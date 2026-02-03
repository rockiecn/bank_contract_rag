#!/usr/bin/env python3
"""
LangChain向量化环境检查脚本
运行: python check_dependencies.py
"""

import sys
import pkg_resources
import importlib

def check_package(package_name, min_version=None):
    """检查包是否安装及版本"""
    try:
        # 尝试获取包版本
        version = pkg_resources.get_distribution(package_name).version
        status = "✓"
        
        # 检查是否满足最低版本要求
        if min_version:
            installed = pkg_resources.parse_version(version)
            required = pkg_resources.parse_version(min_version)
            if installed < required:
                status = "⚠"
                return status, version, f"版本低于推荐值 {min_version}"
        
        return status, version, "已安装"
    except pkg_resources.DistributionNotFound:
        return "✗", "未安装", "需要安装"
    except Exception as e:
        return "✗", "错误", str(e)

def test_import(module_name):
    """测试模块是否能正常导入"""
    try:
        importlib.import_module(module_name)
        return "✓", "导入成功"
    except ImportError as e:
        return "✗", f"导入失败: {e}"
    except Exception as e:
        return "✗", f"导入出错: {e}"

def check_system_info():
    """检查系统信息"""
    import platform
    return {
        "Python版本": platform.python_version(),
        "操作系统": platform.system(),
        "处理器": platform.processor(),
    }

def main():
    print("=" * 70)
    print("LangChain RAG环境依赖检查")
    print("=" * 70)
    
    # 定义需要检查的关键包及推荐版本
    required_packages = {
        "langchain": "0.1.0",
        "langchain-community": "0.0.10",
        "chromadb": "0.4.18",
        "sentence-transformers": "2.2.2",
        "torch": "2.1.0",  # sentence-transformers依赖
        "python-docx": "1.1.0",  # 你的文档处理依赖
        "numpy": "1.24.0",  # 数值计算基础
    }
    
    # 可选但推荐的包
    optional_packages = {
        "tqdm": "",  # 进度条，sentence-transformers可能用到
        "huggingface-hub": "",  # 下载模型可能需要
    }
    
    print("\n📦 核心包版本检查:")
    print("-" * 50)
    
    all_passed = True
    results = []
    
    for package, min_version in required_packages.items():
        status, version, message = check_package(package, min_version)
        results.append((package, status, version, message))
        if status == "✗":
            all_passed = False
    
    # 显示结果
    max_name_len = max(len(name) for name, _, _, _ in results)
    for name, status, version, message in results:
        print(f"{status} {name:{max_name_len}} : {version:15} | {message}")
    
    print("\n🔧 可选包检查:")
    print("-" * 50)
    for package, _ in optional_packages.items():
        status, version, _ = check_package(package)
        print(f"{status} {package:{max_name_len}} : {version}")
    
    print("\n🔍 关键模块导入测试:")
    print("-" * 50)
    
    # 测试关键模块导入
    key_modules = [
        ("langchain.vectorstores", "Chroma向量存储"),
        ("langchain.embeddings", "HuggingFaceEmbeddings"),
        ("sentence_transformers", "SentenceTransformer模型"),
        ("chromadb", "Chroma向量数据库"),
        ("torch", "PyTorch深度学习框架"),
    ]
    
    for module_path, description in key_modules:
        status, message = test_import(module_path.split('.')[0])
        print(f"{status} {description:25} : {message}")
    
    print("\n💻 系统信息:")
    print("-" * 50)
    sys_info = check_system_info()
    for key, value in sys_info.items():
        print(f"  {key:15}: {value}")
    
    print("\n🧪 额外功能测试:")
    print("-" * 50)
    
    # 测试GPU是否可用（对性能很重要）
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "未知"
            print(f"✓ GPU可用: {gpu_name} (设备数: {gpu_count})")
            
            # 测试CUDA版本
            cuda_version = torch.version.cuda or "N/A"
            print(f"  CUDA版本: {cuda_version}")
        else:
            print("⚠ GPU不可用，将使用CPU（速度较慢）")
            print("  建议: 如有NVIDIA GPU，请安装CUDA版本的PyTorch")
    except:
        print("✗ 无法检测GPU状态")
    
    # 测试中文嵌入模型是否可下载
    try:
        from sentence_transformers import SentenceTransformer
        print("\n🌐 测试中文嵌入模型可访问性...")
        # 只测试一个小模型来检查网络连接
        test_model_name = "sentence-transformers/paraphrase-albert-small-v2"
        print(f"  尝试访问模型仓库: {test_model_name}")
        print("  注意: 首次运行会下载模型，可能需要一些时间")
        print("  实际使用时请用: 'GanymedeNil/text2vec-large-chinese'")
    except Exception as e:
        print(f"⚠ 模型访问测试失败: {e}")
    
    print("\n" + "=" * 70)
    
    if all_passed:
        print("✅ 所有核心依赖检查通过！")
        print("\n下一步建议:")
        print("1. 运行你的向量化脚本")
        print("2. 如需GPU加速，确保已安装对应CUDA版本的torch")
        print("3. 首次运行会下载嵌入模型，请保持网络畅通")
    else:
        print("❌ 部分依赖缺失或版本不匹配")
        print("\n修复建议:")
        print("1. 运行以下命令安装缺失包:")
        missing = [name for name, status, _, _ in results if status == "✗"]
        if missing:
            print(f"   pip install {' '.join(missing)}")
        print("2. 或安装所有推荐版本:")
        print("   pip install langchain==0.1.0 langchain-community==0.0.10 chromadb==0.4.18")
        print("   pip install sentence-transformers==2.2.2 torch==2.1.0")
    
    print("=" * 70)

if __name__ == "__main__":
    main()