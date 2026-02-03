"""
创建向量数据库脚本（改进版）
功能：初始化一个空的向量数据库，设置正确的数据结构和元信息
"""

import sys
import json
from pathlib import Path
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

# ==================== LangChain 导入 ====================
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

# ==================== 本地导入 ====================
# 假设我们有一个共享的嵌入模型模块
try:
    from embeddings import Text2VecEmbeddings
except ImportError:
    # 如果不存在，定义一个简化版本
    print("⚠️  警告: 未找到embeddings模块，使用简化嵌入模型")
    from langchain.embeddings import HuggingFaceEmbeddings as Text2VecEmbeddings


class VectorDBCreator:
    """
    向量数据库创建器
    用于初始化向量数据库，设置集合和索引
    """
    
    def __init__(self, model_path: str = "/root/models/text2vec-large-chinese"):
        """
        初始化创建器
        """
        print(f"🧠 初始化向量数据库创建器...")
        print(f"   模型路径: {model_path}")
        
        # 验证模型路径
        model_dir = Path(model_path)
        if not model_dir.exists():
            print(f"❌ 错误: 模型目录不存在: {model_path}")
            sys.exit(1)
        
        # 创建嵌入模型实例
        try:
            self.embeddings = Text2VecEmbeddings(model_path=model_path)
            print(f"✅ 嵌入模型加载成功")
        except Exception as e:
            print(f"❌ 嵌入模型加载失败: {e}")
            sys.exit(1)
    
    def create_database(self, persist_directory: str = "./chroma_contract_db", 
                       collection_name: str = "contract_law_documents"):
        """
        创建向量数据库，并初始化集合
        
        参数:
        persist_directory: 数据库持久化目录
        collection_name: 集合名称
        """
        print(f"\n🔨 正在创建向量数据库...")
        print(f"   保存路径: {persist_directory}")
        print(f"   集合名称: {collection_name}")
        
        # 确保目录存在
        persist_path = Path(persist_directory)
        persist_path.mkdir(parents=True, exist_ok=True)
        
        # 创建或加载集合
        try:
            # 检查是否已经存在集合
            existing_collections = self._get_existing_collections(persist_directory)
            
            if collection_name in existing_collections:
                print(f"⚠️  警告: 集合 '{collection_name}' 已存在")
                choice = input("   是否重新创建？(y/n): ")
                if choice.lower() != 'y':
                    print("   使用现有集合...")
                    return self._load_existing_db(persist_directory, collection_name)
            
            # 创建一个空的向量数据库
            print(f"   创建新的集合: {collection_name}")
            
            # 创建一个空的文档列表
            empty_documents = []
            
            # 创建带metadata的示例文档，用于初始化数据库结构
            init_metadata = {
                "db_version": "2.0",
                "created_at": datetime.now().isoformat(),
                "total_files": 0,
                "last_updated": datetime.now().isoformat(),
                "model_info": "text2vec-large-chinese"
            }
            
            # 初始化文档（可以添加一个系统文档）
            system_doc = Document(
                page_content="这是一个合同和法律文档向量数据库。",
                metadata={
                    **init_metadata,
                    "source": "system",
                    "type": "system_info",
                    "clause_header": "数据库信息"
                }
            )
            
            # 创建向量数据库
            vectorstore = Chroma.from_documents(
                documents=[system_doc],
                embedding=self.embeddings,
                persist_directory=persist_directory,
                collection_name=collection_name,
                collection_metadata={
                    "hnsw:space": "cosine",
                    "description": "合同和法律文档向量数据库",
                    "version": "2.0",
                    "created": datetime.now().isoformat()
                }
            )
            
            # 持久化
            vectorstore.persist()
            
            # 保存数据库配置
            self._save_db_config(persist_directory, {
                "collection_name": collection_name,
                "embedding_model": "text2vec-large-chinese",
                "created_at": datetime.now().isoformat(),
                "version": "2.0",
                "total_documents": 1,
                "index_type": "hnsw",
                "similarity_metric": "cosine"
            })
            
            print(f"\n✅ 向量数据库创建成功！")
            print(f"   📍 存储位置: {persist_directory}")
            print(f"   📁 集合名称: {collection_name}")
            print(f"   📊 初始文档: 1 个 (系统文档)")
            
            # 测试检索
            print(f"\n🧪 测试数据库功能...")
            self._test_database(vectorstore)
            
            return vectorstore
            
        except Exception as e:
            print(f"❌ 创建向量数据库时出错: {e}")
            raise
    
    def _get_existing_collections(self, persist_directory: str) -> list:
        """获取已存在的集合列表"""
        try:
            # 尝试加载数据库查看现有集合
            # Chroma 默认使用 'chroma' 作为客户端
            import chromadb
            client = chromadb.PersistentClient(path=persist_directory)
            collections = client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            # 如果目录不存在或没有集合，返回空列表
            return []
    
    def _load_existing_db(self, persist_directory: str, collection_name: str):
        """加载已存在的数据库"""
        print(f"📂 加载现有数据库...")
        try:
            vectorstore = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings,
                collection_name=collection_name
            )
            
            # 获取文档数量
            doc_count = vectorstore._collection.count()
            print(f"✅ 数据库加载成功")
            print(f"   文档数量: {doc_count}")
            
            return vectorstore
        except Exception as e:
            print(f"❌ 加载数据库失败: {e}")
            raise
    
    def _save_db_config(self, persist_directory: str, config: Dict[str, Any]):
        """保存数据库配置"""
        config_path = Path(persist_directory) / "db_config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def _test_database(self, vectorstore):
        """测试数据库功能"""
        try:
            # 测试检索
            test_query = "合同数据库"
            results = vectorstore.similarity_search(test_query, k=1)
            
            if results:
                print(f"✅ 检索测试通过")
                print(f"   查询: '{test_query}'")
                print(f"   返回: {len(results)} 个结果")
            else:
                print(f"⚠️  检索测试返回空结果")
                
            # 测试获取文档数量
            doc_count = vectorstore._collection.count()
            print(f"✅ 文档计数: {doc_count}")
            
        except Exception as e:
            print(f"❌ 数据库测试失败: {e}")


def main():
    """主函数：创建向量数据库"""
    print("=" * 70)
    print("📚 向量数据库初始化工具 v2.0")
    print("功能：创建新的向量数据库（ChromaDB）")
    print("=" * 70)
    
    # ==================== 配置参数 ====================
    # 根据实际情况修改这些路径
    LOCAL_MODEL_PATH = "/root/models/text2vec-large-chinese"  # 本地模型路径
    PERSIST_DIR = "../../knowledge_base"  # 向量数据库保存目录
    COLLECTION_NAME = "contract_law_collection"  # 集合名称
    
    # ==================== 执行流程 ====================
    print(f"\n📁 配置信息:")
    print(f"   模型路径: {LOCAL_MODEL_PATH}")
    print(f"   数据库位置: {PERSIST_DIR}")
    print(f"   集合名称: {COLLECTION_NAME}")
    
    # 1. 初始化创建器
    print(f"\n1. 🚀 初始化向量数据库创建器...")
    creator = VectorDBCreator(model_path=LOCAL_MODEL_PATH)
    
    # 2. 创建数据库
    print(f"\n2. 🏗️  创建向量数据库...")
    try:
        vectorstore = creator.create_database(
            persist_directory=PERSIST_DIR,
            collection_name=COLLECTION_NAME
        )
    except Exception as e:
        print(f"❌ 创建向量数据库失败: {e}")
        sys.exit(1)
    
    # ==================== 总结与后续步骤 ====================
    print("\n" + "=" * 70)
    print("🎉 向量数据库初始化完成！")
    print("=" * 70)
    
    print(f"\n📊 数据库信息:")
    print(f"   位置: {PERSIST_DIR}")
    print(f"   集合: {COLLECTION_NAME}")
    print(f"   嵌入模型: text2vec-large-chinese")
    print(f"   相似度: 余弦相似度")
    
    print(f"\n💡 后续步骤:")
    print(f"   运行 'python import_to_vector_db.py' 导入文档数据")
    print(f"   此数据库支持增量导入，不会重复添加相同文件")
    
    print(f"\n✅ 初始化完成！")


if __name__ == "__main__":
    main()