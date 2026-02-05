#!/usr/bin/env python3
"""
检索模块 - 基于现有测试代码封装
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
    """知识库检索器 - 封装版"""
    
    def __init__(
        self,
        kb_path: str = "../../knowledge_base",
        embedding_model_path: str = "/root/models/text2vec-large-chinese",
        collection_name: str = "contract_law_collection"
    ):
        """初始化检索器"""
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
        """将文本转换为向量"""
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
        """查询知识库"""
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
        """文本检索（简化接口）"""
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
            # 显示前150个字符，加上相似度
            preview = doc[:150] + "..." if len(doc) > 150 else doc
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
            logger.error(f"获取集合信息失败: {e}")
            return {}