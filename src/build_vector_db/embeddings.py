"""
共享嵌入模型模块
统一嵌入模型接口
"""

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from langchain_core.embeddings import Embeddings
from typing import List


class Text2VecEmbeddings(Embeddings):
    """Text2Vec嵌入模型封装"""
    
    def __init__(self, model_path: str = "/root/models/text2vec-large-chinese", 
                 batch_size: int = 32, max_length: int = 512):
        print(f"🧠 加载Text2Vec模型: {model_path}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self.model.eval()
        
        self.batch_size = batch_size
        self.max_length = max_length
        
        print(f"✅ 模型加载完成，设备: {self.device}")
    
    def _encode_batch(self, texts: List[str]) -> np.ndarray:
        """编码一批文本"""
        encoded_input = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        encoded_input = {k: v.to(self.device) for k, v in encoded_input.items()}
        
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        
        # 平均池化
        last_hidden_state = model_output.last_hidden_state
        attention_mask = encoded_input['attention_mask']
        
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        sum_embeddings = torch.sum(last_hidden_state * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        embeddings = sum_embeddings / sum_mask
        
        # 转换为numpy并归一化
        embeddings = embeddings.cpu().numpy()
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms
        
        return embeddings
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """为文档列表生成嵌入"""
        if not texts:
            return []
        
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_embeddings = self._encode_batch(batch_texts)
            all_embeddings.append(batch_embeddings)
        
        if all_embeddings:
            all_embeddings = np.vstack(all_embeddings)
        
        return all_embeddings.tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """为查询生成嵌入"""
        if not text:
            return []
        embeddings = self._encode_batch([text])
        return embeddings[0].tolist()