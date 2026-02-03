"""
智能增量导入向量数据库脚本
功能：扫描目录，智能检测文件变更，避免重复导入
"""

import json
import os
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple
import sys

# ==================== LangChain 导入 ====================
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

# ==================== 本地导入 ====================
try:
    from embeddings import Text2VecEmbeddings
except ImportError:
    print("⚠️  警告: 未找到embeddings模块")
    sys.exit(1)


class SmartDocumentImporter:
    """
    智能文档导入器
    支持增量导入和重复检测
    """
    
    def __init__(self, model_path: str = "/root/models/text2vec-large-chinese"):
        """
        初始化导入器
        """
        print(f"🧠 初始化智能文档导入器...")
        
        # 嵌入模型
        self.embeddings = Text2VecEmbeddings(model_path=model_path)
        
        # 导入统计
        self.stats = {
            'scanned_files': 0,
            'new_files': 0,
            'modified_files': 0,
            'unchanged_files': 0,
            'failed_files': 0,
            'total_chunks': 0,
            'added_chunks': 0
        }
        
        # 记录已处理的文件哈希
        self.processed_files_log = Path("./processed_files.log")
        
        print(f"✅ 导入器初始化完成")
    
    def load_vector_db(self, persist_directory: str, collection_name: str = "contract_law_collection"):
        """
        加载向量数据库
        """
        print(f"\n📂 加载向量数据库...")
        print(f"   路径: {persist_directory}")
        print(f"   集合: {collection_name}")
        
        if not Path(persist_directory).exists():
            print(f"❌ 错误: 数据库目录不存在: {persist_directory}")
            print("   请先运行 create_vector_db.py 创建数据库")
            sys.exit(1)
        
        try:
            self.vectorstore = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings,
                collection_name=collection_name
            )
            
            # 获取当前文档数量
            current_count = self.vectorstore._collection.count()
            print(f"✅ 数据库加载成功")
            print(f"   当前文档数量: {current_count}")
            
            return self.vectorstore
            
        except Exception as e:
            print(f"❌ 加载数据库失败: {e}")
            sys.exit(1)
    
    def scan_directories(self, directories: List[str]) -> List[Path]:
        """
        扫描目录，返回所有JSON文件
        """
        print(f"\n🔍 扫描目录...")
        
        all_files = []
        for dir_path in directories:
            dir_path_obj = Path(dir_path)
            
            if not dir_path_obj.exists():
                print(f"⚠️  警告: 目录不存在: {dir_path}")
                continue
            
            print(f"   扫描: {dir_path}")
            
            # 递归查找所有JSON文件
            for json_file in dir_path_obj.rglob("*.json"):
                all_files.append(json_file)
            
            print(f"     找到 {len([f for f in dir_path_obj.rglob('*.json')])} 个文件")
        
        self.stats['scanned_files'] = len(all_files)
        print(f"\n📊 总共找到 {len(all_files)} 个JSON文件")
        
        return all_files
    
    def compute_file_hash(self, file_path: Path) -> str:
        """
        计算文件的MD5哈希值
        用于检测文件是否被修改
        """
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
            return hashlib.md5(file_content).hexdigest()
        except Exception as e:
            print(f"❌ 计算文件哈希失败 {file_path}: {e}")
            return ""
    
    def load_processed_files(self) -> Dict[str, Dict[str, Any]]:
        """
        加载已处理文件的记录
        返回: {文件路径: {哈希值, 处理时间, 文档数}}
        """
        processed_files = {}
        
        if self.processed_files_log.exists():
            try:
                with open(self.processed_files_log, 'r', encoding='utf-8') as f:
                    processed_files = json.load(f)
                print(f"📖 加载了 {len(processed_files)} 个已处理文件记录")
            except Exception as e:
                print(f"⚠️  加载处理记录失败: {e}")
        
        return processed_files
    
    def save_processed_files(self, processed_files: Dict[str, Dict[str, Any]]):
        """
        保存已处理文件记录
        """
        try:
            with open(self.processed_files_log, 'w', encoding='utf-8') as f:
                json.dump(processed_files, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存处理记录失败: {e}")
    
    def is_file_already_processed(self, file_path: Path, current_hash: str, 
                                 processed_files: Dict[str, Dict[str, Any]]) -> Tuple[bool, bool]:
        """
        检查文件是否已处理过
        返回: (是否已处理, 是否需要更新)
        """
        file_str = str(file_path)
        
        if file_str not in processed_files:
            return False, False  # 新文件
        
        old_hash = processed_files[file_str].get('hash', '')
        
        if old_hash == current_hash:
            return True, False  # 已处理，无需更新
        else:
            return True, True  # 已处理，但文件已修改，需要更新
    
    def load_documents_from_json(self, json_path: Path) -> List[Document]:
        """
        从JSON文件加载文档块
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                chunks_data = json.load(f)
            
            documents = []
            for i, chunk in enumerate(chunks_data):
                text = chunk.get('text', '')
                if not text:
                    continue
                
                metadata = chunk.get('metadata', {})
                
                # 添加文件信息
                metadata.update({
                    'source_file': str(json_path),
                    'file_name': json_path.name,
                    'chunk_index': i,
                    'total_chunks': len(chunks_data),
                    'import_time': datetime.now().isoformat()
                })
                
                doc = Document(page_content=text, metadata=metadata)
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            print(f"❌ 加载文件失败 {json_path}: {e}")
            return []
    
    def remove_old_documents(self, file_path: Path):
        """
        删除指定文件对应的旧文档
        通过metadata中的source_file字段查找
        """
        try:
            file_str = str(file_path)
            
            # 通过metadata过滤查找文档
            # 注意：Chroma的delete操作需要where过滤器
            results = self.vectorstore.get(where={"source_file": file_str})
            
            if results and len(results['ids']) > 0:
                doc_count = len(results['ids'])
                print(f"   删除 {doc_count} 个旧文档")
                
                # 删除文档
                self.vectorstore.delete(ids=results['ids'])
                
                return doc_count
            else:
                return 0
                
        except Exception as e:
            print(f"⚠️  删除旧文档失败 {file_path}: {e}")
            return 0
    
    def import_file(self, file_path: Path, processed_files: Dict[str, Dict[str, Any]], 
                   delete_after_import: bool = True) -> bool:
        """
        导入单个文件到向量数据库
        """
        print(f"\n📄 处理: {file_path.name}")
        
        # 1. 计算文件哈希
        current_hash = self.compute_file_hash(file_path)
        if not current_hash:
            self.stats['failed_files'] += 1
            return False
        
        # 2. 检查文件是否已处理
        is_processed, needs_update = self.is_file_already_processed(
            file_path, current_hash, processed_files
        )
        
        if is_processed and not needs_update:
            print(f"   ⏭️  文件未修改，跳过")
            self.stats['unchanged_files'] += 1
            return True
        
        # 3. 加载文档
        documents = self.load_documents_from_json(file_path)
        if not documents:
            print(f"   ⚠️  文件为空或格式错误")
            self.stats['failed_files'] += 1
            return False
        
        # 4. 如果是更新，先删除旧文档
        if needs_update:
            removed_count = self.remove_old_documents(file_path)
            print(f"   🔄 文件已修改，删除 {removed_count} 个旧文档")
            self.stats['modified_files'] += 1
        else:
            print(f"   ✨ 新文件，准备导入")
            self.stats['new_files'] += 1
        
        # 5. 导入新文档
        try:
            print(f"   正在导入 {len(documents)} 个文档块...")
            
            # 分批导入以避免内存问题
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i + batch_size]
                
                # 提取文本和元数据
                texts = [doc.page_content for doc in batch_docs]
                metadatas = [doc.metadata for doc in batch_docs]
                
                # 添加到向量数据库
                self.vectorstore.add_texts(texts=texts, metadatas=metadatas)
                
                progress = min(i + batch_size, len(documents)) / len(documents) * 100
                if len(documents) > batch_size:
                    print(f"     🔄 进度: {progress:.1f}%")
            
            # 6. 更新处理记录
            processed_files[str(file_path)] = {
                'hash': current_hash,
                'processed_at': datetime.now().isoformat(),
                'document_count': len(documents),
                'file_size': os.path.getsize(file_path)
            }
            
            # 7. 删除或备份源文件
            # if delete_after_import:
            #     self._backup_or_delete_file(file_path)
            
            # 8. 更新统计
            self.stats['total_chunks'] += len(documents)
            self.stats['added_chunks'] += len(documents)
            
            print(f"   ✅ 导入成功 ({len(documents)} 个文档块)")
            return True
            
        except Exception as e:
            print(f"❌ 导入失败: {e}")
            self.stats['failed_files'] += 1
            return False
    
    def _backup_or_delete_file(self, file_path: Path):
        """
        备份或删除源文件
        """
        try:
            # # 创建备份目录
            # backup_dir = Path("./backup_imported_files")
            # backup_dir.mkdir(exist_ok=True)
            
            # # 备份文件（保留目录结构）
            # relative_path = file_path.relative_to(file_path.parent.parent.parent)
            # backup_path = backup_dir / relative_path
            
            # # 确保备份目录存在
            # backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # # 移动文件
            # shutil.move(str(file_path), str(backup_path))
            # print(f"   📦 文件已备份到: {backup_path}")
            
            # 可选：删除空目录
            try:
                if file_path.parent.exists() and not any(file_path.parent.iterdir()):
                    file_path.parent.rmdir()
            except:
                pass
                
        except Exception as e:
            print(f"⚠️  文件备份失败: {e}")
            # 如果备份失败，至少删除源文件
            try:
                file_path.unlink()
                print(f"   🗑️  源文件已删除")
            except:
                print(f"   ⚠️  无法删除源文件")
    
    def import_directories(self, directories: List[str], delete_after_import: bool = True):
        """
        导入指定目录下的所有文件
        """
        print(f"\n🚀 开始智能导入...")
        
        # 1. 扫描文件
        all_files = self.scan_directories(directories)
        if not all_files:
            print("❌ 没有找到任何JSON文件")
            return
        
        # 2. 加载处理记录
        processed_files = self.load_processed_files()
        
        # 3. 导入每个文件
        success_count = 0
        for i, file_path in enumerate(all_files):
            print(f"\n[{i+1}/{len(all_files)}] ", end="")
            
            success = self.import_file(
                file_path, 
                processed_files, 
                delete_after_import
            )
            
            if success:
                success_count += 1
        
        # 4. 保存处理记录
        self.save_processed_files(processed_files)
        
        # 5. 持久化向量数据库
        print(f"\n💾 保存向量数据库...")
        self.vectorstore.persist()
        print(f"✅ 数据库已保存")
        
        # 6. 打印统计
        self._print_statistics()
        
        return success_count
    
    def _print_statistics(self):
        """打印导入统计信息"""
        print("\n" + "=" * 70)
        print("📊 智能导入统计报告")
        print("=" * 70)
        
        print(f"\n📁 文件统计:")
        print(f"   扫描文件: {self.stats['scanned_files']}")
        print(f"   ├─ 新文件: {self.stats['new_files']}")
        print(f"   ├─ 修改文件: {self.stats['modified_files']}")
        print(f"   ├─ 未修改文件: {self.stats['unchanged_files']}")
        print(f"   └─ 失败文件: {self.stats['failed_files']}")
        
        print(f"\n📄 文档块统计:")
        print(f"   总文档块: {self.stats['total_chunks']}")
        print(f"   新增文档块: {self.stats['added_chunks']}")
        
        if self.stats['scanned_files'] > 0:
            success_rate = (self.stats['new_files'] + self.stats['modified_files']) / self.stats['scanned_files'] * 100
            print(f"\n📈 处理成功率: {success_rate:.1f}%")
    
    def test_retrieval(self, test_queries: List[str] = None):
        """
        测试检索功能
        """
        if test_queries is None:
            test_queries = [
                "贷款人违约有什么后果？",
                "借款人违约有什么后果？",
            ]
        
        print(f"\n🧪 测试检索功能...")
        
        for query in test_queries:
            print(f"\n🔍 查询: '{query}'")
            try:
                results = self.vectorstore.similarity_search(query, k=2)
                
                if results:
                    print(f"   找到 {len(results)} 个相关结果:")
                    for i, doc in enumerate(results):
                        source = doc.metadata.get('source_file', '未知')
                        clause = doc.metadata.get('clause_header', '未知条款')
                        
                        # 简略显示
                        file_name = Path(source).name if source != '未知' else '未知'
                        preview = doc.page_content[:60] + "..." if len(doc.page_content) > 60 else doc.page_content
                        print(f"     {i+1}. [{file_name}] {clause}: {preview}")
                else:
                    print(f"   未找到相关结果")
                    
            except Exception as e:
                print(f"   检索失败: {e}")


def main():
    """主函数：智能增量导入文档"""
    print("=" * 70)
    print("📚 智能文档导入工具 v2.0")
    print("功能：增量导入JSON文档到向量数据库，避免重复")
    print("=" * 70)
    
    # ==================== 配置参数 ====================
    LOCAL_MODEL_PATH = "/root/models/text2vec-large-chinese"
    PERSIST_DIR = "../../knowledge_base"
    COLLECTION_NAME = "contract_law_collection"
    
    # 要扫描的目录列表
    SCAN_DIRECTORIES = [
        "../../docs/chunks/law_chunks",
        "../../docs/chunks/contract_chunks"
    ]
    
    # 是否导入后删除源文件
    DELETE_AFTER_IMPORT = True
    
    # ==================== 执行流程 ====================
    print(f"\n📁 配置信息:")
    print(f"   模型路径: {LOCAL_MODEL_PATH}")
    print(f"   数据库位置: {PERSIST_DIR}")
    print(f"   集合名称: {COLLECTION_NAME}")
    print(f"   扫描目录: {SCAN_DIRECTORIES}")
    print(f"   导入后删除源文件: {'是' if DELETE_AFTER_IMPORT else '否'}")
    
    # 1. 初始化导入器
    print(f"\n1. 🚀 初始化智能导入器...")
    importer = SmartDocumentImporter(model_path=LOCAL_MODEL_PATH)
    
    # 2. 加载向量数据库
    print(f"\n2. 📂 加载向量数据库...")
    vectorstore = importer.load_vector_db(PERSIST_DIR, COLLECTION_NAME)
    
    # 获取当前文档数量
    current_count = vectorstore._collection.count()
    print(f"   当前文档数量: {current_count}")
    
    # 3. 确认操作
    print(f"\n⚠️  确认操作:")
    print(f"   将扫描 {len(SCAN_DIRECTORIES)} 个目录")
    print(f"   数据库当前有 {current_count} 个文档")
    
    confirm = input("   是否继续？(y/n): ")
    if confirm.lower() != 'y':
        print("操作取消")
        sys.exit(0)
    
    # 4. 导入文档
    print(f"\n3. 🚀 开始智能导入...")
    success_count = importer.import_directories(
        directories=SCAN_DIRECTORIES,
        delete_after_import=DELETE_AFTER_IMPORT
    )
    
    # 5. 测试检索
    print(f"\n4. 🧪 测试检索功能...")
    new_count = vectorstore._collection.count()
    print(f"   更新后文档总数: {new_count}")
    print(f"   本次新增文档: {new_count - current_count}")
    
    if new_count > current_count:
        importer.test_retrieval()
    
    # ==================== 总结 ====================
    print("\n" + "=" * 70)
    print("🎉 智能导入完成！")
    print("=" * 70)
    
    print(f"\n💡 功能特点:")
    print(f"   • 文件哈希检测: 避免重复导入相同文件")
    print(f"   • 增量更新: 只处理新增或修改的文件")
    print(f"   • 记录跟踪: 已处理文件记录在 processed_files.log")
    
    print(f"\n📊 数据库状态:")
    print(f"   文档总数: {new_count}")
    print(f"   位置: {PERSIST_DIR}")
    print(f"   下次运行: 只会处理新增或修改的文件")
    
    print(f"\n✅ 完成！")


if __name__ == "__main__":
    main()