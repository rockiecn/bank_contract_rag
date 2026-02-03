#!/usr/bin/env python3
"""
修复后的知识库检索测试脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KnowledgeBaseRetriever:
    """知识库检索器"""
    
    def __init__(
        self,
        kb_path: str = "../../knowledge_base",  # 修改为正确的路径
        embedding_model_path: str = "/root/models/text2vec-large-chinese",
        collection_name: str = "contract_law_collection"  # 使用正确的集合名称
    ):
        """
        初始化检索器
        
        Args:
            kb_path: ChromaDB知识库路径
            embedding_model_path: 向量模型路径
            collection_name: 集合名称
        """
        self.kb_path = kb_path
        self.embedding_model_path = embedding_model_path
        
        # 初始化向量模型
        logger.info(f"加载向量模型: {embedding_model_path}")
        self.embedding_model = SentenceTransformer(embedding_model_path)
        
        # 初始化ChromaDB客户端
        logger.info(f"连接知识库: {kb_path}")
        self.client = chromadb.PersistentClient(
            path=kb_path,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        # 获取集合
        self.collection_name = collection_name
        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"加载集合: {self.collection_name}")
        except Exception as e:
            logger.error(f"集合不存在: {e}")
            # 列出所有可用集合
            collections = self.client.list_collections()
            logger.info(f"可用集合: {[c.name for c in collections]}")
            
            if collections:
                # 使用第一个可用集合
                self.collection = collections[0]
                self.collection_name = self.collection.name
                logger.info(f"使用集合: {self.collection_name}")
            else:
                raise ValueError(f"知识库中没有找到任何集合")
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        将文本转换为向量
        """
        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings.tolist()
    
    def query_knowledge_base(
        self,
        query: str,
        n_results: int = 3,
        where_filter: Dict = None,
        where_document_filter: Dict = None
    ) -> Dict[str, Any]:
        """
        查询知识库
        """
        logger.info(f"查询: {query}")
        
        # 获取查询向量
        query_embedding = self.get_embeddings([query])[0]
        
        # 执行查询
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            where_document=where_document_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        return results
    
    def search_by_text(
        self,
        query: str,
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        文本检索（简化接口）
        """
        raw_results = self.query_knowledge_base(query, n_results)
        
        formatted_results = []
        if raw_results and raw_results['documents']:
            for i in range(len(raw_results['documents'][0])):
                result = {
                    'document': raw_results['documents'][0][i],
                    'metadata': raw_results['metadatas'][0][i] if raw_results['metadatas'] else {},
                    'distance': raw_results['distances'][0][i] if raw_results['distances'] else None,
                    'similarity': 1 - raw_results['distances'][0][i] if raw_results['distances'] else None
                }
                formatted_results.append(result)
        
        return formatted_results
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            count = self.collection.count()
            
            # 获取样本以查看元数据字段
            metadata_fields = set()
            if count > 0:
                sample = self.collection.peek(limit=1)
                if sample['metadatas'] and sample['metadatas'][0]:
                    metadata_fields = set(sample['metadatas'][0].keys())
            
            return {
                'name': self.collection_name,
                'count': count,
                'metadata_fields': list(metadata_fields)
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}

def print_results(results: List[Dict[str, Any]]):
    """打印检索结果"""
    if not results:
        print("未找到相关结果")
        return
    
    print(f"\n找到 {len(results)} 个相关结果:")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        print(f"\n结果 {i}:")
        print(f"相似度: {result.get('similarity', 0):.4f}")
        print(f"距离: {result.get('distance', 0):.4f}")
        
        # 打印元数据
        metadata = result.get('metadata', {})
        if metadata:
            print("元数据:")
            for key, value in metadata.items():
                if key in ['import_time', 'source', 'clause_header']:  # 只显示关键字段
                    print(f"  {key}: {value}")
        
        # 打印文档内容
        document = result.get('document', '')
        print("内容:")
        print("-" * 40)
        # 显示前200个字符
        preview = document[:200] + "..." if len(document) > 200 else document
        print(preview)
        print("-" * 40)

def test_bank_contract_queries(retriever: KnowledgeBaseRetriever):
    """银行合同相关查询测试"""
    print("\n" + "=" * 80)
    print("银行合同相关查询测试")
    print("=" * 80)
    
    # 银行合同相关的测试查询
    test_queries = [
        "贷款利率",
        "违约责任",
        "担保条款",
        "抵押物",
        "提前还款",
        "争议解决",
        "违约金",
        "保证责任"
    ]
    
    for query in test_queries:
        print(f"\n查询: '{query}'")
        results = retriever.search_by_text(query, n_results=2)
        print_results(results)

def main():
    """主函数"""
    print("银行合同知识库检索测试")
    print("=" * 80)
    
    try:
        # 初始化检索器
        retriever = KnowledgeBaseRetriever(
            kb_path="../../knowledge_base",  # 从src/test_db目录的相对路径
            embedding_model_path="/root/models/text2vec-large-chinese",
            collection_name="contract_law_collection"
        )
        
        # 显示知识库信息
        collection_info = retriever.get_collection_info()
        print(f"知识库信息:")
        print(f"  集合名称: {collection_info.get('name', '未知')}")
        print(f"  文档数量: {collection_info.get('count', 0)}")
        print(f"  元数据字段: {collection_info.get('metadata_fields', [])}")
        
        # 运行测试
        test_bank_contract_queries(retriever)
        
        print("\n" + "=" * 80)
        print("测试完成!")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    # 注意：运行此脚本需要设置LD_PRELOAD环境变量
    # 例如: LD_PRELOAD=/root/anaconda3/envs/kb/lib/libstdc++.so.6 python test_retrieval.py
    
    print("注意：请确保设置了LD_PRELOAD环境变量")
    print("例如: LD_PRELOAD=/root/anaconda3/envs/kb/lib/libstdc++.so.6 python test_retrieval.py")
    print()
    
    exit(main())