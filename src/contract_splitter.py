import os
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path
from docx import Document
import json

class ContractTextSplitter:
    """合同文档专用文本分割器，针对合同特点优化"""
    
    def __init__(self, chunk_size=1000, chunk_overlap=150, min_chunk_length=30):
        """
        初始化合同分割器
        
        Args:
            chunk_size: 块大小（合同通常条款较长）
            chunk_overlap: 块重叠大小
            min_chunk_length: 最小块长度
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length
        
        # 合同专用条款识别模式（优先级从高到低）
        self.contract_clause_patterns = [
            # 1. 合同专用条款：第一条、第1条
            (r'第[一二三四五六七八九十百千万零]+条[^\n]*', '中文条款', 1),
            (r'第\d+条[^\n]*', '数字条款', 2),
            
            # 2. 合同章节：第一章、第一节
            (r'第[一二三四五六七八九十]+章[^\n]*', '章节标题', 3),
            (r'第[一二三四五六七八九十]+节[^\n]*', '小节标题', 4),
            
            # 3. 合同当事人信息（重要部分）
            (r'^甲方[：:][^\n]*', '甲方信息', 5),
            (r'^乙方[：:][^\n]*', '乙方信息', 6),
            (r'^借款人[：:][^\n]*', '借款人信息', 7),
            (r'^贷款人[：:][^\n]*', '贷款人信息', 8),
            (r'^出借人[：:][^\n]*', '出借人信息', 9),
            (r'^保证人[：:][^\n]*', '保证人信息', 10),
            
            # 4. 合同核心条款标题
            (r'^贷款金额[：:][^\n]*', '金额条款', 11),
            (r'^贷款利率[：:][^\n]*', '利率条款', 12),
            (r'^还款方式[：:][^\n]*', '还款条款', 13),
            (r'^违约责任[：:][^\n]*', '违约条款', 14),
            (r'^争议解决[：:][^\n]*', '争议条款', 15),
            (r'^担保条款[：:][^\n]*', '担保条款', 16),
            (r'^保密条款[：:][^\n]*', '保密条款', 17),
            
            # 5. 编号条款：1.、1.1、(1)、①
            (r'^\d+[\.、][^\n]*', '数字编号', 18),
            (r'^\d+\.\d+[^\n]*', '小数编号', 19),
            (r'^[（(][一二三四五六七八九十\d]+[）)][^\n]*', '括号编号', 20),
            (r'^[①②③④⑤⑥⑦⑧⑨⑩][^\n]*', '带圈编号', 21),
            
            # 6. 中文序号：一、二、
            (r'^[一二三四五六七八九十]+[、.][^\n]*', '中文序号', 22),
            
            # 7. 大写金额和数字（合同特有）
            (r'人民币[零壹贰叁肆伍陆柒捌玖拾佰仟万亿元整]+[^\n]*', '大写金额', 23),
            (r'¥\s*\d+[,\d]*\.?\d*[^\n]*', '货币金额', 24),
            
            # 8. 日期条款（合同重要信息）
            (r'^\d{4}年\d{1,2}月\d{1,2}日[^\n]*', '日期条款', 25),
            (r'^[合同协议]期[限间][：:][^\n]*', '期限条款', 26),
        ]
        
        # 合同关键词，用于识别条款类型
        self.contract_keywords = {
            '当事人': '当事人信息',
            '贷款': '贷款条款',
            '借款': '借款条款',
            '还款': '还款条款',
            '利息': '利息条款',
            '利率': '利率条款',
            '担保': '担保条款',
            '抵押': '抵押条款',
            '质押': '质押条款',
            '保证': '保证条款',
            '违约': '违约条款',
            '赔偿': '赔偿条款',
            '争议': '争议条款',
            '仲裁': '仲裁条款',
            '诉讼': '诉讼条款',
            '保密': '保密条款',
            '生效': '生效条款',
            '终止': '终止条款',
            '解除': '解除条款',
            '通知': '通知条款',
            '送达': '送达条款',
            '附件': '附件条款',
            '签字': '签字条款',
            '盖章': '盖章条款',
        }
    
    def split_by_contract_clauses(self, text: str) -> List[Dict[str, Any]]:
        """
        按合同条款分割文本，返回带元数据的块列表
        
        Args:
            text: 要分割的文本
            
        Returns:
            分割后的条款列表，每个条款包含文本和元数据
        """
        if not text or not text.strip():
            return []
        
        # 查找所有可能的条款开始位置
        clause_positions = self._find_all_clause_positions(text)
        
        # 如果没有找到条款，尝试按段落分割
        if not clause_positions:
            return self._split_by_paragraphs(text)
        
        # 按条款位置分割
        clauses = []
        
        # 处理第一个条款之前的内容（如果有）
        if clause_positions[0][0] > 0:
            pre_text = text[:clause_positions[0][0]].strip()
            if pre_text and len(pre_text) >= self.min_chunk_length:
                clause_type = self._detect_clause_type(pre_text)
                clauses.append({
                    'text': pre_text,
                    'type': clause_type,
                    'header': '合同前言',
                    'priority': 0
                })
        
        # 按条款位置分割
        for i in range(len(clause_positions)):
            start_pos, header, clause_type, priority = clause_positions[i]
            
            # 确定结束位置
            if i + 1 < len(clause_positions):
                end_pos = clause_positions[i+1][0]
            else:
                end_pos = len(text)
            
            # 提取条款文本
            clause_text = text[start_pos:end_pos].strip()
            
            if clause_text and len(clause_text) >= self.min_chunk_length:
                clauses.append({
                    'text': clause_text,
                    'type': clause_type,
                    'header': header.strip(),
                    'priority': priority
                })
        
        return clauses
    
    def _find_all_clause_positions(self, text: str) -> List[Tuple[int, str, str, int]]:
        """查找所有合同条款的位置"""
        clause_positions = []
        
        # 使用所有模式查找
        for pattern, clause_type, priority in self.contract_clause_patterns:
            try:
                for match in re.finditer(pattern, text, re.MULTILINE):
                    start_pos = match.start()
                    header = match.group().strip()
                    
                    # 检查是否已经记录过相似位置（避免重复）
                    if not self._is_position_already_recorded(start_pos, clause_positions):
                        clause_positions.append((start_pos, header, clause_type, priority))
            except re.error:
                continue
        
        # 按位置排序
        clause_positions.sort(key=lambda x: x[0])
        
        return clause_positions
    
    def _is_position_already_recorded(self, position: int, positions: List[Tuple]) -> bool:
        """检查位置是否已经被记录过"""
        for pos, _, _, _ in positions:
            if abs(position - pos) < 5:  # 允许5个字符的误差
                return True
        return False
    
    def _detect_clause_type(self, text: str) -> str:
        """根据内容检测条款类型"""
        first_line = text.split('\n')[0] if '\n' in text else text
        first_line = first_line.strip()
        
        # 检查是否匹配已知模式
        for pattern, clause_type, _ in self.contract_clause_patterns:
            if re.match(pattern, first_line):
                return clause_type
        
        # 检查是否包含合同关键词
        for keyword, clause_type in self.contract_keywords.items():
            if keyword in first_line[:50]:  # 只检查前50个字符
                return clause_type
        
        # 根据内容长度判断
        if len(text) < 100:
            return '短条款'
        elif len(text) < 300:
            return '中等条款'
        else:
            return '长条款'
    
    def _split_by_paragraphs(self, text: str) -> List[Dict[str, Any]]:
        """按段落分割文本（当找不到明显条款时使用）"""
        if not text:
            return []
        
        # 分割段落（两个以上换行）
        paragraphs = re.split(r'\n\s*\n+', text)
        clauses = []
        
        for para in paragraphs:
            para = para.strip()
            if para and len(para) >= self.min_chunk_length:
                clause_type = self._detect_clause_type(para)
                
                # 提取段落第一行作为标题
                header = para.split('\n')[0].strip()
                if len(header) > 50:
                    header = header[:50] + "..."
                
                clauses.append({
                    'text': para,
                    'type': clause_type,
                    'header': header,
                    'priority': 999  # 低优先级
                })
        
        return clauses
    
    def identify_contract_party(self, text: str) -> str:
        """识别合同当事人类型"""
        if re.search(r'甲方[：:]', text[:200]):
            return '甲方'
        elif re.search(r'乙方[：:]', text[:200]):
            return '乙方'
        elif re.search(r'借款人[：:]', text[:200]):
            return '借款人'
        elif re.search(r'贷款人[：:]', text[:200]):
            return '贷款人'
        elif re.search(r'出借人[：:]', text[:200]):
            return '出借人'
        elif re.search(r'保证人[：:]', text[:200]):
            return '保证人'
        elif re.search(r'抵押人[：:]', text[:200]):
            return '抵押人'
        else:
            return '其他'

class ContractDocumentProcessor:
    """合同文档处理器，专门处理合同文档"""
    
    def __init__(self, contracts_dir: str = "../docs/contracts", chunk_size=1000, min_chunk_length=30):
        """
        初始化合同处理器
        
        Args:
            contracts_dir: 合同文档目录路径
            chunk_size: 块大小（字符数）
            min_chunk_length: 最小块长度
        """
        self.contracts_dir = Path(contracts_dir)
        self.docs = []
        self.splitter = ContractTextSplitter(
            chunk_size=chunk_size, 
            min_chunk_length=min_chunk_length
        )
    
    def extract_docx_text(self, file_path: Path) -> Dict[str, Any]:
        """从docx文件中提取合同文本"""
        try:
            doc = Document(file_path)
            
            # 提取所有段落
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
            full_text = '\n\n'.join(paragraphs)
            
            # 尝试提取合同标题（用于显示，不作为文件夹名）
            contract_title = "未命名合同"
            if paragraphs:
                # 检查前几行是否有"合同"、"协议"等关键词
                for i in range(min(5, len(paragraphs))):
                    line = paragraphs[i]
                    if any(keyword in line for keyword in ['合同', '协议', '协议书', '契约', '合约', '约定书']):
                        contract_title = line.strip()
                        if len(contract_title) > 100:
                            contract_title = contract_title[:100] + "..."
                        break
                else:
                    # 如果没有找到，使用文件名（不含扩展名）
                    contract_title = Path(file_path).stem
            
            return {
                'file_name': file_path.name,  # 带扩展名的文件名
                'file_stem': Path(file_path).stem,  # 不含扩展名的文件名
                'contract_title': contract_title,
                'file_path': str(file_path),
                'full_text': full_text,
                'total_paragraphs': len(paragraphs),
                'extraction_success': True
            }
        except Exception as e:
            print(f"提取合同文件 {file_path} 时出错: {e}")
            return {
                'file_name': file_path.name,
                'file_stem': Path(file_path).stem,
                'contract_title': "提取失败",
                'file_path': str(file_path),
                'full_text': '',
                'error': str(e),
                'extraction_success': False
            }
    
    def load_all_documents(self) -> List[Dict[str, Any]]:
        """加载目录中的所有合同文档"""
        if not self.contracts_dir.exists():
            print(f"合同目录不存在: {self.contracts_dir}")
            return []
        
        # 支持多种文档扩展名
        extensions = ["*.docx", "*.doc"]
        contract_files = []
        for ext in extensions:
            contract_files.extend(list(self.contracts_dir.glob(ext)))
        
        print(f"找到 {len(contract_files)} 个合同文件")
        
        all_docs = []
        for file_path in contract_files:
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
        """处理并分割所有合同文档"""
        if not self.docs:
            self.load_all_documents()
        
        all_chunks = []
        
        for doc in self.docs:
            if not doc['extraction_success']:
                continue
            
            print(f"分割合同: {doc['file_stem']} ({doc['file_name']})")
            
            # 使用合同专用分割器
            clauses = self.splitter.split_by_contract_clauses(doc['full_text'])
            
            print(f"  分割为 {len(clauses)} 个条款")
            
            # 统计条款类型
            clause_types = {}
            for clause in clauses:
                clause_type = clause['type']
                clause_types[clause_type] = clause_types.get(clause_type, 0) + 1
            
            # 显示主要条款类型
            if clause_types:
                main_types = sorted(clause_types.items(), key=lambda x: x[1], reverse=True)[:3]
                print(f"  主要条款类型: {', '.join([f'{t[0]}({t[1]})' for t in main_types])}")
            
            # 添加元数据
            for i, clause in enumerate(clauses):
                # 识别当事人
                party = self.splitter.identify_contract_party(clause['text'])
                
                all_chunks.append({
                    'text': clause['text'],
                    'metadata': {
                        'source': doc['file_name'],
                        'source_stem': doc['file_stem'],  # 添加不含扩展名的文件名
                        'contract_title': doc['contract_title'],
                        'file_path': doc['file_path'],
                        'chunk_index': i,
                        'total_chunks_in_doc': len(clauses),
                        'chunk_size': len(clause['text']),
                        'clause_type': clause['type'],
                        'clause_header': clause['header'],
                        'contract_party': party,
                        'clause_priority': clause['priority'],
                        'chunk_preview': clause['text'][:120].replace('\n', ' ') + ("..." if len(clause['text']) > 120 else "")
                    }
                })
        
        return all_chunks
    
    def save_results(self, chunks: List[Dict[str, Any]], output_dir: str = "./contract_chunks"):
        """保存合同分割结果 - 按合同文件名（不含扩展名）创建文件夹"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 按合同分组
        contracts_groups = {}
        for chunk in chunks:
            source = chunk['metadata']['source']
            if source not in contracts_groups:
                contracts_groups[source] = []
            contracts_groups[source].append(chunk)
        
        # 为每个合同创建文件夹并保存
        contract_folders = {}
        folder_names_used = {}  # 用于记录已使用的文件夹名，避免重复
        
        for source, contract_chunks in contracts_groups.items():
            # 使用文件名（不含扩展名）作为文件夹名
            file_stem = contract_chunks[0]['metadata']['source_stem'] if contract_chunks else Path(source).stem
            
            # 清理文件夹名中的非法字符
            safe_folder_name = self._make_valid_folder_name(file_stem)
            
            # 检查是否已有同名文件夹，如果有则添加序号
            original_name = safe_folder_name
            counter = 1
            while safe_folder_name in folder_names_used:
                safe_folder_name = f"{original_name}_{counter}"
                counter += 1
            
            folder_names_used[safe_folder_name] = True
            
            contract_folder = output_path / safe_folder_name
            contract_folder.mkdir(exist_ok=True)
            
            contract_folders[source] = {
                'folder_path': str(contract_folder),
                'folder_name': safe_folder_name,
                'file_stem': file_stem,
                'contract_title': contract_chunks[0]['metadata']['contract_title'] if contract_chunks else "未命名合同"
            }
            
            # 按块索引排序
            contract_chunks.sort(key=lambda x: x['metadata']['chunk_index'])
            
            # 保存该合同的块到自己的文件夹
            contract_json_path = contract_folder / "chunks.json"
            with open(contract_json_path, 'w', encoding='utf-8') as f:
                json.dump(contract_chunks, f, ensure_ascii=False, indent=2)
            
            # 保存该合同的统计信息
            contract_stats_path = contract_folder / "statistics.txt"
            with open(contract_stats_path, 'w', encoding='utf-8') as f:
                self._write_contract_statistics(f, source, contract_chunks)
            
            # 显示保存信息
            contract_title = contract_chunks[0]['metadata']['contract_title'] if contract_chunks else "未命名合同"
            print(f"  ✓ 合同 '{contract_title}' 的分割结果已保存到: {contract_folder}/")
        
        # 保存总的统计信息
        stats_path = output_path / "contracts_split_statistics.txt"
        with open(stats_path, 'w', encoding='utf-8') as f:
            self._write_overall_statistics(f, chunks, contracts_groups, contract_folders)
        
        print(f"✓ 总体统计信息已保存到: {stats_path}")
        
        return str(output_path)
    
    def _make_valid_folder_name(self, name: str) -> str:
        """将字符串转换为有效的文件夹名"""
        if not name:
            return "未命名合同"
        
        # 移除非法文件名字符
        invalid_chars = r'[<>:"/\\|?*\n\r\t]'
        valid_name = re.sub(invalid_chars, '_', name)
        
        # 移除首尾空格和点
        valid_name = valid_name.strip('. ')
        
        # 移除连续的下划线
        valid_name = re.sub(r'_+', '_', valid_name)
        
        # 限制长度
        if len(valid_name) > 80:
            valid_name = valid_name[:80]
        
        # 如果清理后为空，使用默认名称
        if not valid_name or valid_name.isspace():
            valid_name = "未命名合同"
        
        return valid_name
    
    def _write_contract_statistics(self, f, source: str, contract_chunks: List[Dict[str, Any]]):
        """写入单个合同的统计信息"""
        file_stem = contract_chunks[0]['metadata']['source_stem'] if contract_chunks else Path(source).stem
        contract_title = contract_chunks[0]['metadata']['contract_title'] if contract_chunks else "未命名合同"
        
        f.write("=" * 80 + "\n")
        f.write(f"合同分割统计\n")
        f.write(f"合同文件: {source}\n")
        f.write(f"文件名(不含扩展名): {file_stem}\n")
        f.write(f"合同标题: {contract_title}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"📊 合同统计\n")
        f.write(f"  合同文件: {source}\n")
        f.write(f"  文件名: {file_stem}\n")
        f.write(f"  合同标题: {contract_title}\n")
        f.write(f"  条款总数: {len(contract_chunks)}\n")
        
        if contract_chunks:
            avg_chunk_size = sum(len(c['text']) for c in contract_chunks) / len(contract_chunks)
            max_chunk_size = max(len(c['text']) for c in contract_chunks)
            min_chunk_size = min(len(c['text']) for c in contract_chunks)
            
            f.write(f"  平均条款大小: {avg_chunk_size:.0f} 字符\n")
            f.write(f"  最大条款大小: {max_chunk_size} 字符\n")
            f.write(f"  最小条款大小: {min_chunk_size} 字符\n")
            
            # 按条款类型统计
            clause_types = {}
            party_stats = {}
            for chunk in contract_chunks:
                clause_type = chunk['metadata']['clause_type']
                clause_types[clause_type] = clause_types.get(clause_type, 0) + 1
                
                party = chunk['metadata']['contract_party']
                party_stats[party] = party_stats.get(party, 0) + 1
            
            f.write(f"\n📋 条款类型统计\n")
            for clause_type, count in sorted(clause_types.items(), key=lambda x: x[1], reverse=True):
                percentage = count / len(contract_chunks) * 100
                f.write(f"  {clause_type}: {count} 条 ({percentage:.1f}%)\n")
            
            f.write(f"\n👥 当事人分布\n")
            for party, count in sorted(party_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = count / len(contract_chunks) * 100
                f.write(f"  {party}: {count} 条 ({percentage:.1f}%)\n")
            
            # 检查连续性
            indices = [c['metadata']['chunk_index'] for c in contract_chunks]
            if indices:
                min_idx = min(indices)
                max_idx = max(indices)
                
                # 找出缺失的索引
                all_indices = set(range(min_idx, max_idx + 1))
                present_indices = set(indices)
                missing_indices = sorted(all_indices - present_indices)
                
                if missing_indices:
                    f.write(f"\n⚠ 连续性检查\n")
                    f.write(f"  缺失条款索引: {missing_indices}\n")
                    f.write(f"  缺失条款数量: {len(missing_indices)}\n")
            
            # 列出重要条款（高优先级）
            f.write(f"\n🔍 重要条款列表\n")
            important_clauses = [c for c in contract_chunks if c['metadata']['clause_priority'] <= 15]
            
            if important_clauses:
                f.write(f"  共找到 {len(important_clauses)} 个重要条款:\n")
                for chunk in important_clauses[:15]:  # 只显示前15个
                    idx = chunk['metadata']['chunk_index']
                    clause_type = chunk['metadata']['clause_type']
                    header = chunk['metadata']['clause_header']
                    size = chunk['metadata']['chunk_size']
                    
                    f.write(f"  条款 {idx:3d}: [{clause_type}] {header[:40]} ({size:4d}字符)\n")
            else:
                f.write(f"  未识别到重要条款\n")
            
            # 列出所有条款
            f.write(f"\n{'─' * 60}\n")
            f.write(f"完整条款列表 (共{len(contract_chunks)}个条款):\n")
            f.write(f"{'─' * 60}\n")
            
            for chunk in contract_chunks:
                idx = chunk['metadata']['chunk_index']
                clause_type = chunk['metadata']['clause_type']
                header = chunk['metadata']['clause_header']
                party = chunk['metadata']['contract_party']
                size = chunk['metadata']['chunk_size']
                
                # 提取预览文本
                preview = chunk['text'][:80].replace('\n', ' ')
                if len(chunk['text']) > 80:
                    preview += "..."
                
                f.write(f"条款 {idx:3d}: [{party}][{clause_type}] {header} ({size:4d}字符)\n")
                if chunk['metadata']['clause_priority'] <= 10:
                    f.write(f"      预览: {preview}\n")
    
    def _write_overall_statistics(self, f, chunks: List[Dict[str, Any]], 
                                 contracts_groups: Dict[str, List], contract_folders: Dict[str, dict]):
        """写入总体统计信息"""
        f.write("=" * 80 + "\n")
        f.write("合同文档分割总体统计报告\n")
        f.write("=" * 80 + "\n\n")
        
        # 总体统计
        f.write(f"📊 总体统计\n")
        f.write(f"  合同总数: {len(contracts_groups)}\n")
        f.write(f"  条款总数: {len(chunks)}\n")
        
        if chunks:
            avg_chunk_size = sum(len(c['text']) for c in chunks) / len(chunks)
            f.write(f"  平均条款大小: {avg_chunk_size:.0f} 字符\n")
        
        # 各合同统计摘要
        f.write(f"\n📁 各合同统计摘要\n")
        for source, contract_chunks in contracts_groups.items():
            contract_info = contract_folders.get(source, {})
            file_stem = contract_info.get('file_stem', Path(source).stem) if contract_info else Path(source).stem
            contract_title = contract_info.get('contract_title', '未命名合同') if contract_info else '未命名合同'
            folder_path = contract_info.get('folder_path', '') if contract_info else ''
            avg_size = sum(len(c['text']) for c in contract_chunks) / len(contract_chunks) if contract_chunks else 0
            
            # 统计重要条款数量
            important_clauses = [c for c in contract_chunks if c['metadata']['clause_priority'] <= 15]
            
            f.write(f"\n  📄 文件: {source}\n")
            f.write(f"    文件名: {file_stem}\n")
            f.write(f"    合同标题: {contract_title}\n")
            f.write(f"    条款数: {len(contract_chunks)}\n")
            f.write(f"    重要条款: {len(important_clauses)}\n")
            f.write(f"    平均条款大小: {avg_size:.0f} 字符\n")
            f.write(f"    保存位置: {folder_path}/\n")
        
        # 条款类型分布
        f.write(f"\n📋 总体条款类型分布\n")
        clause_types = {}
        for chunk in chunks:
            clause_type = chunk['metadata']['clause_type']
            clause_types[clause_type] = clause_types.get(clause_type, 0) + 1
        
        for clause_type, count in sorted(clause_types.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(chunks) * 100
            f.write(f"  {clause_type}: {count} 条 ({percentage:.1f}%)\n")
        
        # 当事人分布
        f.write(f"\n👥 总体当事人分布\n")
        parties = {}
        for chunk in chunks:
            party = chunk['metadata']['contract_party']
            parties[party] = parties.get(party, 0) + 1
        
        for party, count in sorted(parties.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(chunks) * 100
            f.write(f"  {party}: {count} 条 ({percentage:.1f}%)\n")
        
        # 保存位置信息
        f.write(f"\n💾 文件保存位置\n")
        f.write(f"  总统计文件: {Path.cwd() / 'contract_chunks' / 'contracts_split_statistics.txt'}\n")
        f.write(f"  各合同分割结果:\n")
        for source, info in contract_folders.items():
            file_stem = info.get('file_stem', Path(source).stem)
            folder_path = info.get('folder_path', '')
            f.write(f"    • {file_stem}: {folder_path}/\n")

def main():
    """主函数"""
    print("=" * 80)
    print("通用合同文档分割器 - 按合同文件名命名文件夹")
    print("=" * 80)
    
    # 配置参数
    import argparse
    
    parser = argparse.ArgumentParser(description="通用合同文档分割器")
    parser.add_argument("--input-dir", default="../docs/contracts_cleaned", help="输入合同目录")
    parser.add_argument("--output-dir", default="../docs/chunks/contract_chunks", help="输出目录")
    parser.add_argument("--chunk-size", type=int, default=1000, help="条款大小（字符数）")
    parser.add_argument("--min-length", type=int, default=30, help="最小条款长度")
    
    args = parser.parse_args()
    
    # 初始化处理器
    processor = ContractDocumentProcessor(
        contracts_dir=args.input_dir,
        chunk_size=args.chunk_size,
        min_chunk_length=args.min_length
    )
    
    # 1. 加载合同
    print(f"\n[步骤1] 从 '{args.input_dir}' 加载合同文档...")
    contracts = processor.load_all_documents()
    
    if not contracts:
        print("❌ 没有找到可处理的合同。请检查:")
        print(f"   1. 目录是否存在: {args.input_dir}")
        print(f"   2. 目录中是否有.docx或.doc文件")
        print(f"   3. 确保合同文档放在正确目录")
        return
    
    print(f"✅ 成功加载 {len(contracts)} 个合同")
    
    # 2. 分割合同
    print(f"\n[步骤2] 按条款分割合同...")
    chunks = processor.process_documents()
    print(f"✅ 总分割条款数: {len(chunks)}")
    
    # 3. 保存结果
    print(f"\n[步骤3] 保存分割结果到 '{args.output_dir}'...")
    print("  按合同文件名（不含扩展名）创建文件夹，保存分割结果:")
    output_path = processor.save_results(chunks, args.output_dir)
    
    # 4. 显示总结
    print(f"\n" + "=" * 80)
    print("处理完成!")
    print("=" * 80)
    
    # 显示处理结果
    if chunks:
        print(f"\n📋 处理摘要:")
        print(f"  • 输入合同: {len(contracts)} 个")
        print(f"  • 输出条款: {len(chunks)} 条")
        print(f"  • 输出目录: {output_path}")
        
        # 显示各合同的输出位置
        print(f"\n📁 各合同输出位置:")
        for contract in contracts:
            if contract['extraction_success']:
                file_stem = contract['file_stem']
                safe_name = processor._make_valid_folder_name(file_stem)
                
                # 检查是否有同名文件夹，如果有则添加序号
                contract_folder = Path(output_path) / safe_name
                if not contract_folder.exists():
                    # 如果没有找到，可能是因为有编号后缀，尝试查找
                    matching_folders = list(Path(output_path).glob(f"{safe_name}*"))
                    if matching_folders:
                        contract_folder = matching_folders[0]
                
                if contract_folder.exists():
                    print(f"  • {file_stem}: {contract_folder.name}/")

if __name__ == "__main__":
    main()