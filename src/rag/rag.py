#!/usr/bin/env python3
"""
银行合同审查AI - 完整修复版
解决所有已知问题
"""

import sys
import os
import json
import argparse
import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
import re

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# API配置
API_URL = "http://localhost:8000/chat"

def clean_document_content(doc: str) -> str:
    """清理文档内容，移除相似度信息等"""
    if not doc:
        return ""
    
    # 移除相似度信息
    doc = re.sub(r'\[相似度: [0-9.]+\]', '', doc)
    
    # 移除方括号内容（保留中文字符）
    doc = re.sub(r'\[[^\]]*\]', '', doc)
    
    # 标准化空白
    doc = re.sub(r'\s+', ' ', doc)
    
    return doc.strip()

def call_chatglm2_api(prompt: str, temperature: float = 0.7) -> Optional[str]:
    """
    调用ChatGLM2 API - 修复版
    """
    print(f"调用API: {len(prompt)}字符, temperature={temperature}")
    
    # 根据Prompt长度动态设置超时
    prompt_len = len(prompt)
    if prompt_len < 100:
        read_timeout = 30
    elif prompt_len < 300:
        read_timeout = 60
    elif prompt_len < 500:
        read_timeout = 120
    else:
        read_timeout = 180
    
    print(f"设置超时: 10秒连接, {read_timeout}秒读取")
    
    payload = {
        "prompt": prompt,
        "temperature": temperature
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=(10, read_timeout)
        )
        elapsed_time = time.time() - start_time
        
        print(f"响应时间: {elapsed_time:.2f}秒")
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "")
        else:
            print(f"HTTP错误: {response.status_code}")
            print(f"错误响应: {response.text[:200]}")
            return None
    
    except requests.exceptions.Timeout:
        print(f"请求超时 (连接10秒/读取{read_timeout}秒)")
        return None
    except Exception as e:
        print(f"请求错误: {e}")
        return None

def build_optimized_prompt(user_clause: str, retrieved_knowledge: str) -> str:
    """
    构建优化的Prompt
    """
    # 清理检索结果
    lines = retrieved_knowledge.split('\n')
    cleaned_refs = []
    
    for line in lines:
        if line and not line.startswith('【'):
            # 清理内容
            cleaned = clean_document_content(line)
            if cleaned:
                # 如果还有编号，移除它
                if '. ' in cleaned:
                    cleaned = cleaned.split('. ', 1)[1]
                cleaned_refs.append(cleaned[:80])  # 限制长度
    
    # 构建参考资料部分
    if cleaned_refs:
        references = "【参考资料】\n" + "\n".join([f"{i+1}. {ref}" for i, ref in enumerate(cleaned_refs[:3])])
    else:
        references = "【参考资料】\n无相关参考资料。"
    
    # 构建完整Prompt
    prompt = f"""【角色设定】
你是一名资深银行法律合规官。

【审查任务】
请根据以下参考材料，审查合同条款。

【待审条款】
{user_clause}

{references}

【审查要求】
1. 识别主要风险
2. 指出与标准的差异
3. 给出具体修改建议

【输出格式】
请按以下格式回答：
风险等级：[高/中/低]
风险点：
1. [风险描述]
差异分析：
- [差异点]
修改建议：
[具体修改文本]
复核提示：
[复核事项]"""
    
    return prompt

class KnowledgeBaseRetriever:
    """简化的知识库检索器"""
    
    def __init__(
        self,
        kb_path: str = "../../knowledge_base",
        embedding_model_path: str = "/root/models/text2vec-large-chinese",
        collection_name: str = "contract_law_collection"
    ):
        """初始化检索器"""
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
        
        # 初始化向量模型
        print(f"加载向量模型: {embedding_model_path}")
        self.embedding_model = SentenceTransformer(embedding_model_path)
        
        # 初始化ChromaDB客户端
        print(f"连接知识库: {kb_path}")
        self.client = chromadb.PersistentClient(
            path=kb_path,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        # 获取集合
        self.collection_name = collection_name
        try:
            self.collection = self.client.get_collection(self.collection_name)
            print(f"加载集合: {self.collection_name}")
        except Exception as e:
            print(f"集合不存在: {e}")
            # 使用第一个可用集合
            collections = self.client.list_collections()
            if collections:
                self.collection = collections[0]
                self.collection_name = self.collection.name
                print(f"使用集合: {self.collection_name}")
            else:
                raise ValueError("知识库中没有找到任何集合")
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """将文本转换为向量"""
        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings.tolist()
    
    def search_by_text(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """文本检索"""
        # 获取查询向量
        query_embedding = self.get_embeddings([query])[0]
        
        # 执行查询
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        formatted_results = []
        if results and results['documents']:
            for i in range(len(results['documents'][0])):
                result = {
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else None,
                    'similarity': 1 - results['distances'][0][i] if results['distances'] else None
                }
                formatted_results.append(result)
        
        return formatted_results
    
    def retrieve_for_clause(self, clause_text: str, n_results: int = 3):
        """
        为指定合同条款检索相关知识
        返回：格式化后的检索结果字符串
        """
        raw_results = self.search_by_text(clause_text, n_results)
        return self._format_retrieval_results(raw_results)
    
    def _format_retrieval_results(self, raw_results: List[Dict[str, Any]]):
        """
        将检索结果格式化为适合插入Prompt的文本
        """
        if not raw_results:
            return "知识库中没有找到相关内容。"
        
        formatted = ["【检索到的相关知识】"]
        
        for i, result in enumerate(raw_results, 1):
            doc = result.get('document', '')
            similarity = result.get('similarity', 0)
            
            # 清理文档内容
            doc = clean_document_content(doc)
            
            if doc:
                # 限制长度并添加相似度信息
                preview = doc[:100] + "..." if len(doc) > 100 else doc
                formatted.append(f"{i}. [相似度: {similarity:.3f}] {preview}")
        
        return "\n".join(formatted)
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            count = self.collection.count()
            return {
                'name': self.collection_name,
                'count': count
            }
        except Exception as e:
            print(f"获取集合信息失败: {e}")
            return {}

def run_complete_test(user_clause: str, retriever: KnowledgeBaseRetriever):
    """
    运行完整测试
    """
    print(f"\n{'='*60}")
    print(f"审查条款: {user_clause}")
    print(f"{'='*60}")
    
    # 1. 检索相关知识
    print("\n[1/4] 检索相关知识...")
    try:
        retrieval_results = retriever.retrieve_for_clause(user_clause, n_results=2)
        print(f"检索完成")
    except Exception as e:
        print(f"检索失败: {e}")
        retrieval_results = "检索失败，无参考资料。"
    
    # 2. 构建优化Prompt
    print("[2/4] 构建优化Prompt...")
    enhanced_prompt = build_optimized_prompt(user_clause, retrieval_results)
    
    print(f"Prompt长度: {len(enhanced_prompt)}字符")
    print(f"Prompt预览: {enhanced_prompt[:200]}...")
    
    # 3. 调用API
    print("[3/4] 调用ChatGLM2 API...")
    start_time = time.time()
    response = call_chatglm2_api(enhanced_prompt, temperature=0.1)
    elapsed_time = time.time() - start_time
    
    # 4. 输出结果
    if response:
        print(f"[4/4] 完成! 耗时: {elapsed_time:.1f}秒")
        print(f"\n{'='*60}")
        print("审查结果:")
        print(f"{'='*60}")
        print(response)
        print(f"{'='*60}")
    else:
        print(f"[4/4] 失败! 耗时: {elapsed_time:.1f}秒")
        response = "API调用失败。可能原因：\n1. API服务未运行\n2. Prompt过长导致超时\n3. 网络连接问题"
    
    return {
        "clause": user_clause,
        "retrieved_knowledge": retrieval_results,
        "prompt": enhanced_prompt,
        "response": response,
        "time_seconds": elapsed_time,
        "timestamp": datetime.now().isoformat()
    }

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='银行合同审查AI - 完整修复版')
    parser.add_argument('--clause', type=str, required=True,
                       help='要审查的合同条款文本')
    parser.add_argument('--output', type=str, default=None,
                       help='输出文件路径')
    parser.add_argument('--simple', action='store_true',
                       help='使用简单模式，不调用知识库')
    
    args = parser.parse_args()
    
    print("银行合同审查AI - 完整修复版")
    print("=" * 60)
    
    # 简单模式：直接调用API，不检索知识库
    if args.simple:
        print("使用简单模式...")
        prompt = f"""请审查以下银行合同条款：

{args.clause}

请指出其中的风险并提供修改建议。"""
        
        response = call_chatglm2_api(prompt, temperature=0.1)
        
        if response:
            print(f"\n审查结果:\n{response}")
            
            result = {
                "clause": args.clause,
                "mode": "simple",
                "response": response,
                "timestamp": datetime.now().isoformat()
            }
        else:
            print("API调用失败")
            sys.exit(1)
    else:
        # 完整模式：包含知识库检索
        try:
            # 初始化检索器
            print("初始化知识库检索器...")
            retriever = KnowledgeBaseRetriever(
                kb_path="../../knowledge_base",
                embedding_model_path="/root/models/text2vec-large-chinese",
                collection_name="contract_law_collection"
            )
            
            # 显示知识库信息
            info = retriever.get_collection_info()
            print(f"知识库: {info.get('name', '未知')} ({info.get('count', 0)}条文档)")
            
            # 运行完整测试
            result = run_complete_test(args.clause, retriever)
            
        except Exception as e:
            print(f"初始化失败: {e}")
            print("回退到简单模式...")
            
            # 回退到简单模式
            prompt = f"请审查合同条款: {args.clause}"
            response = call_chatglm2_api(prompt, temperature=0.1)
            
            if response:
                result = {
                    "clause": args.clause,
                    "mode": "fallback_simple",
                    "response": response,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                print("简单模式也失败，退出")
                sys.exit(1)
    
    # 保存结果
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")
        except Exception as e:
            print(f"保存结果失败: {e}")
    
    # 性能分析
    if 'time_seconds' in result:
        print(f"\n性能分析:")
        print(f"  总耗时: {result['time_seconds']:.1f}秒")
        
        if result['time_seconds'] > 60:
            print("  警告: 响应时间过长，建议:")
            print("    1. 使用 --simple 模式")
            print("    2. 缩短合同条款")
            print("    3. 优化知识库文档长度")
        elif result['time_seconds'] > 30:
            print("  注意: 响应时间较长，但可接受")
        else:
            print("  良好: 响应时间在可接受范围内")

if __name__ == "__main__":
    main()