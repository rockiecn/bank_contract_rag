import os
import re
from typing import List, Dict, Any
from pathlib import Path
from docx import Document
import json

class UniversalLegalTextSplitter:
    """通用法律文档文本分割器，适用于各种法律文档格式"""
    
    def __init__(self, chunk_size=800, chunk_overlap=100, min_chunk_length=20):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length
        
        # 通用法律条款识别模式
        self.clause_patterns = [
            # 中文数字条款: 第一条、第一百二十三条
            r'第[一二三四五六七八九十百千万零]+条[^\n]*',
            # 阿拉伯数字条款: 第1条、第123条
            r'第\d+条[^\n]*',
            # 章节标题: 第一章、第十章
            r'第[一二三四五六七八九十]+章[^\n]*',
            # 小节标题: 第一节、第二节
            r'第[一二三四五六七八九十]+节[^\n]*',
            # 带点编号: 1.1、2.3.1
            r'\d+\.\d+(\.\d+)*[^\n]*',
            # 中文序号: 一、二、
            r'[一二三四五六七八九十]+[、.][^\n]*',
            # 括号中文序号: (一)、(二)
            r'[（(][一二三四五六七八九十]+[）)][^\n]*',
            # 括号阿拉伯序号: (1)、(2)
            r'[（(]\d+[）)][^\n]*',
            # 带圈数字: ①、②
            r'[①②③④⑤⑥⑦⑧⑨⑩][^\n]*',
            # 字母编号: a)、b) 或 A、B
            r'[a-zA-Z][)、.][^\n]*',
        ]
    
    def split_by_clauses(self, text: str) -> List[str]:
        """
        按法律条款分割文本，保持条款完整性
        
        Args:
            text: 要分割的文本
            
        Returns:
            分割后的条款列表
        """
        if not text or not text.strip():
            return []
        
        # 组合所有模式
        combined_pattern = '(' + '|'.join(self.clause_patterns) + ')'
        
        # 查找所有条款开始位置
        clause_starts = []
        for pattern in self.clause_patterns:
            for match in re.finditer(pattern, text):
                clause_starts.append((match.start(), match.group()))
        
        # 去重并排序
        clause_starts = sorted(set(clause_starts), key=lambda x: x[0])
        
        # 如果没有找到条款，将整个文本作为一个块
        if not clause_starts:
            return [text.strip()] if len(text.strip()) >= self.min_chunk_length else []
        
        chunks = []
        
        # 处理第一个条款之前的内容
        if clause_starts[0][0] > 0:
            pre_text = text[:clause_starts[0][0]].strip()
            if pre_text and len(pre_text) >= self.min_chunk_length:
                chunks.append(pre_text)
        
        # 按条款分割
        for i in range(len(clause_starts)):
            start_pos, clause_header = clause_starts[i]
            
            # 确定结束位置
            if i + 1 < len(clause_starts):
                end_pos = clause_starts[i+1][0]
            else:
                end_pos = len(text)
            
            # 提取条款文本
            clause_text = text[start_pos:end_pos].strip()
            
            if clause_text and len(clause_text) >= self.min_chunk_length:
                chunks.append(clause_text)
        
        return chunks
    
    def detect_clause_type(self, text: str) -> str:
        """
        检测文本中的条款类型
        
        Args:
            text: 文本内容
            
        Returns:
            条款类型描述
        """
        for i, pattern in enumerate(self.clause_patterns):
            if re.match(pattern, text):
                types = [
                    "中文条款", "数字条款", "章节标题", "小节标题", 
                    "编号条款", "中文序号", "括号中文", "括号数字",
                    "带圈数字", "字母编号"
                ]
                return types[i] if i < len(types) else "未知条款"
        return "普通文本"

class UniversalLegalDocumentProcessor:
    """通用法律文档处理器，适用于各种法律文档格式"""
    
    def __init__(self, laws_dir: str = "../docs/laws", chunk_size=800, min_chunk_length=20):
        """
        初始化处理器
        
        Args:
            laws_dir: 法律文档目录路径
            chunk_size: 块大小（字符数）
            min_chunk_length: 最小块长度
        """
        self.laws_dir = Path(laws_dir)
        self.docs = []
        self.splitter = UniversalLegalTextSplitter(
            chunk_size=chunk_size, 
            min_chunk_length=min_chunk_length
        )
    
    def extract_docx_text(self, file_path: Path) -> Dict[str, Any]:
        """从docx文件中提取文本"""
        try:
            doc = Document(file_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            full_text = '\n\n'.join(paragraphs)
            
            return {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'full_text': full_text,
                'total_paragraphs': len(paragraphs),
                'extraction_success': True
            }
        except Exception as e:
            print(f"提取文件 {file_path} 时出错: {e}")
            return {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'full_text': '',
                'error': str(e),
                'extraction_success': False
            }
    
    def load_all_documents(self) -> List[Dict[str, Any]]:
        """加载目录中的所有docx文档"""
        if not self.laws_dir.exists():
            print(f"目录不存在: {self.laws_dir}")
            return []
        
        # 支持多种文档扩展名
        extensions = ["*.docx", "*.doc"]
        doc_files = []
        for ext in extensions:
            doc_files.extend(list(self.laws_dir.glob(ext)))
        
        print(f"找到 {len(doc_files)} 个文档文件")
        
        all_docs = []
        for file_path in doc_files:
            print(f"正在处理: {file_path.name}")
            doc_data = self.extract_docx_text(file_path)
            
            if doc_data['extraction_success']:
                all_docs.append(doc_data)
                print(f"  ✓ 成功提取，{len(doc_data['full_text'])} 字符")
            else:
                print(f"  ✗ 提取失败: {doc_data.get('error', '未知错误')}")
        
        self.docs = all_docs
        return all_docs
    
    def process_documents(self) -> List[Dict[str, Any]]:
        """处理并分割所有文档"""
        if not self.docs:
            self.load_all_documents()
        
        all_chunks = []
        
        for doc in self.docs:
            if not doc['extraction_success']:
                continue
            
            print(f"分割文档: {doc['file_name']}")
            
            # 使用条款分割
            chunks = self.splitter.split_by_clauses(doc['full_text'])
            
            print(f"  分割为 {len(chunks)} 个块")
            
            # 添加元数据
            for i, chunk in enumerate(chunks):
                # 检测条款类型
                clause_type = self.splitter.detect_clause_type(chunk)
                
                # 提取条款标题（如果存在）
                clause_header = "普通文本"
                if clause_type != "普通文本":
                    # 提取前50个字符作为条款标题
                    clause_header = chunk[:50].split('\n')[0].strip()
                    if len(clause_header) > 30:
                        clause_header = clause_header[:30] + "..."
                
                all_chunks.append({
                    'text': chunk,
                    'metadata': {
                        'source': doc['file_name'],
                        'file_path': doc['file_path'],
                        'chunk_index': i,
                        'total_chunks_in_doc': len(chunks),
                        'chunk_size': len(chunk),
                        'clause_type': clause_type,
                        'clause_header': clause_header,
                        'chunk_preview': chunk[:100].replace('\n', ' ') + ("..." if len(chunk) > 100 else "")
                    }
                })
        
        return all_chunks
    
    def save_results(self, chunks: List[Dict[str, Any]], output_dir: str = "./law_chunks"):
        """保存分割结果 - 按文档名称创建文件夹"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 按文档分组
        docs_groups = {}
        for chunk in chunks:
            source = chunk['metadata']['source']
            if source not in docs_groups:
                docs_groups[source] = []
            docs_groups[source].append(chunk)
        
        # 为每个文档创建文件夹并保存
        doc_folders = {}
        for source, doc_chunks in docs_groups.items():
            # 移除文件扩展名，使用文档名称作为文件夹名
            doc_name = Path(source).stem
            doc_folder = output_path / doc_name
            doc_folder.mkdir(exist_ok=True)
            doc_folders[source] = str(doc_folder)
            
            # 按块索引排序
            doc_chunks.sort(key=lambda x: x['metadata']['chunk_index'])
            
            # 保存该文档的块到自己的文件夹
            doc_json_path = doc_folder / "chunks.json"
            with open(doc_json_path, 'w', encoding='utf-8') as f:
                json.dump(doc_chunks, f, ensure_ascii=False, indent=2)
            
            # 保存该文档的统计信息
            doc_stats_path = doc_folder / "statistics.txt"
            with open(doc_stats_path, 'w', encoding='utf-8') as f:
                self._write_document_statistics(f, source, doc_chunks)
            
            print(f"  ✓ 文档 '{source}' 的分割结果已保存到: {doc_folder}")
        
        # 保存总的统计信息
        stats_path = output_path / "law_split_statistics.txt"
        with open(stats_path, 'w', encoding='utf-8') as f:
            self._write_overall_statistics(f, chunks, docs_groups, doc_folders)
        
        print(f"✓ 总体统计信息已保存到: {stats_path}")
        
        return str(output_path)
    
    def _write_document_statistics(self, f, source: str, doc_chunks: List[Dict[str, Any]]):
        """写入单个文档的统计信息"""
        f.write("=" * 80 + "\n")
        f.write(f"文档分割统计: {source}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"📊 文档统计\n")
        f.write(f"  文档名称: {source}\n")
        f.write(f"  总块数: {len(doc_chunks)}\n")
        
        if doc_chunks:
            avg_chunk_size = sum(len(c['text']) for c in doc_chunks) / len(doc_chunks)
            max_chunk_size = max(len(c['text']) for c in doc_chunks)
            min_chunk_size = min(len(c['text']) for c in doc_chunks)
            
            f.write(f"  平均块大小: {avg_chunk_size:.0f} 字符\n")
            f.write(f"  最大块大小: {max_chunk_size} 字符\n")
            f.write(f"  最小块大小: {min_chunk_size} 字符\n")
            
            # 按条款类型统计
            clause_types = {}
            for chunk in doc_chunks:
                clause_type = chunk['metadata']['clause_type']
                clause_types[clause_type] = clause_types.get(clause_type, 0) + 1
            
            f.write(f"\n📋 条款类型统计\n")
            for clause_type, count in sorted(clause_types.items(), key=lambda x: x[1], reverse=True):
                percentage = count / len(doc_chunks) * 100
                f.write(f"  {clause_type}: {count} 个块 ({percentage:.1f}%)\n")
            
            # 检查连续性
            indices = [c['metadata']['chunk_index'] for c in doc_chunks]
            if indices:
                min_idx = min(indices)
                max_idx = max(indices)
                
                # 找出缺失的索引
                all_indices = set(range(min_idx, max_idx + 1))
                present_indices = set(indices)
                missing_indices = sorted(all_indices - present_indices)
                
                if missing_indices:
                    f.write(f"\n⚠ 连续性检查\n")
                    f.write(f"  缺失块索引: {missing_indices}\n")
                    f.write(f"  缺失块数量: {len(missing_indices)}\n")
            
            # 列出所有块
            f.write(f"\n{'─' * 60}\n")
            f.write(f"详细块列表 (共{len(doc_chunks)}个块):\n")
            f.write(f"{'─' * 60}\n")
            
            for chunk in doc_chunks:
                idx = chunk['metadata']['chunk_index']
                clause_type = chunk['metadata']['clause_type']
                clause_header = chunk['metadata']['clause_header']
                size = chunk['metadata']['chunk_size']
                
                # 提取预览文本
                preview = chunk['text'][:80].replace('\n', ' ')
                if len(chunk['text']) > 80:
                    preview += "..."
                
                f.write(f"块 {idx:3d}: [{clause_type}] {clause_header} ({size:4d}字符)\n")
                f.write(f"     预览: {preview}\n")
    
    def _write_overall_statistics(self, f, chunks: List[Dict[str, Any]], 
                                 docs_groups: Dict[str, List], doc_folders: Dict[str, str]):
        """写入总体统计信息"""
        f.write("=" * 80 + "\n")
        f.write("法律文档分割总体统计报告\n")
        f.write("=" * 80 + "\n\n")
        
        # 总体统计
        f.write(f"📊 总体统计\n")
        f.write(f"  文档总数: {len(docs_groups)}\n")
        f.write(f"  总块数: {len(chunks)}\n")
        
        if chunks:
            avg_chunk_size = sum(len(c['text']) for c in chunks) / len(chunks)
            f.write(f"  平均块大小: {avg_chunk_size:.0f} 字符\n")
        
        # 各文档统计摘要
        f.write(f"\n📁 各文档统计摘要\n")
        for source, doc_chunks in docs_groups.items():
            doc_name = Path(source).stem
            folder_path = doc_folders[source]
            avg_size = sum(len(c['text']) for c in doc_chunks) / len(doc_chunks) if doc_chunks else 0
            
            f.write(f"\n  📄 文档: {source}\n")
            f.write(f"    块数: {len(doc_chunks)}\n")
            f.write(f"    平均块大小: {avg_size:.0f} 字符\n")
            f.write(f"    保存位置: {folder_path}/\n")
            
            # 检查连续性
            indices = [c['metadata']['chunk_index'] for c in doc_chunks]
            if indices:
                min_idx = min(indices)
                max_idx = max(indices)
                expected_count = max_idx - min_idx + 1
                actual_count = len(doc_chunks)
                
                if expected_count != actual_count:
                    f.write(f"    ⚠ 连续性警告: 应有{expected_count}个块，实际{actual_count}个块\n")
        
        # 条款类型分布
        f.write(f"\n📋 总体条款类型分布\n")
        clause_types = {}
        for chunk in chunks:
            clause_type = chunk['metadata']['clause_type']
            clause_types[clause_type] = clause_types.get(clause_type, 0) + 1
        
        for clause_type, count in sorted(clause_types.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(chunks) * 100
            f.write(f"  {clause_type}: {count} 个块 ({percentage:.1f}%)\n")
        
        # 保存位置信息
        f.write(f"\n💾 文件保存位置\n")
        f.write(f"  总统计文件: {Path.cwd() / 'law_chunks' / 'split_statistics.txt'}\n")
        f.write(f"  各文档分割结果:\n")
        for source, folder_path in doc_folders.items():
            f.write(f"    • {source}: {folder_path}/\n")

def main():
    """主函数"""
    print("=" * 80)
    print("通用法律文档分割器")
    print("=" * 80)
    
    # 配置参数
    import argparse
    
    parser = argparse.ArgumentParser(description="通用法律文档分割器")
    parser.add_argument("--input-dir", default="../docs/laws_cleaned", help="输入文档目录")
    parser.add_argument("--output-dir", default="../docs/chunks/law_chunks", help="输出目录")
    parser.add_argument("--chunk-size", type=int, default=800, help="块大小（字符数）")
    parser.add_argument("--min-length", type=int, default=20, help="最小块长度")
    
    args = parser.parse_args()
    
    # 初始化处理器
    processor = UniversalLegalDocumentProcessor(
        laws_dir=args.input_dir,
        chunk_size=args.chunk_size,
        min_chunk_length=args.min_length
    )
    
    # 1. 加载文档
    print(f"\n[步骤1] 从 '{args.input_dir}' 加载法律文档...")
    docs = processor.load_all_documents()
    
    if not docs:
        print("❌ 没有找到可处理的文档。请检查:")
        print(f"   1. 目录是否存在: {args.input_dir}")
        print(f"   2. 目录中是否有.docx或.doc文件")
        return
    
    print(f"✅ 成功加载 {len(docs)} 个文档")
    
    # 2. 分割文档
    print(f"\n[步骤2] 按条款分割文档...")
    chunks = processor.process_documents()
    print(f"✅ 总分割块数: {len(chunks)}")
    
    # 3. 保存结果
    print(f"\n[步骤3] 保存分割结果到 '{args.output_dir}'...")
    print("  按文档名称创建文件夹，保存分割结果:")
    output_path = processor.save_results(chunks, args.output_dir)
    
    # 4. 显示总结
    print(f"\n" + "=" * 80)
    print("处理完成!")
    print("=" * 80)
    
    # 显示处理结果
    if chunks:
        print(f"\n📋 处理摘要:")
        print(f"  • 输入文档: {len(docs)} 个")
        print(f"  • 输出块数: {len(chunks)} 个")
        print(f"  • 输出目录: {output_path}")
        
        # 显示各文档的输出位置
        print(f"\n📁 各文档输出位置:")
        import os
        for doc in docs:
            if doc['extraction_success']:
                doc_name = Path(doc['file_name']).stem
                doc_folder = Path(output_path) / doc_name
                if doc_folder.exists():
                    print(f"  • {doc['file_name']}: {doc_folder}/")

if __name__ == "__main__":
    main()