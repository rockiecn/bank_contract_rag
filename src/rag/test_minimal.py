#!/usr/bin/env python3
"""
最小可行测试：验证问题是否出在检索结果的格式上
"""

import requests
import json

def test_minimal():
    """最小可行测试"""
    
    # 测试1: 使用原始检索结果（可能有问题）
    problematic_prompt = """【角色设定】
你是一名资深银行法律合规官。

【待审条款】
借款利率为年化6%，按季结息，到期一次性还本

【参考资料】
1. [相似度: 0.687] 第一百九十六条　借款合同是借款人向贷款人借款，到期返还借款并支付利息的合同。
2. [相似度: 0.665] 第六百七十六条　借款人未按照约定的期限返还借款的，应当按照约定或者国家有关规定支付逾期利息。
3. [相似度: 0.660] 第六百六十七条　借款合同是借款人向贷款人借款，到期返还借款并支付利息的合同。

请审查上述条款。"""
    
    # 测试2: 使用清理后的检索结果
    cleaned_prompt = """【角色设定】
你是一名资深银行法律合规官。

【待审条款】
借款利率为年化6%，按季结息，到期一次性还本

【参考资料】
1. 第一百九十六条　借款合同是借款人向贷款人借款，到期返还借款并支付利息的合同。
2. 第六百七十六条　借款人未按照约定的期限返还借款的，应当按照约定或者国家有关规定支付逾期利息。
3. 第六百六十七条　借款合同是借款人向贷款人借款，到期返还借款并支付利息的合同。

请审查上述条款。"""
    
    api_url = "http://localhost:8000/chat"
    
    print("测试1: 使用带相似度信息的Prompt")
    print(f"Prompt长度: {len(problematic_prompt)}")
    
    try:
        response = requests.post(api_url, 
            json={"prompt": problematic_prompt, "temperature": 0.7}, 
            timeout=30)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("✓ 成功")
        else:
            print("✗ 失败")
    except Exception as e:
        print(f"✗ 超时或错误: {e}")
    
    print("\n测试2: 使用清理后的Prompt")
    print(f"Prompt长度: {len(cleaned_prompt)}")
    
    try:
        response = requests.post(api_url, 
            json={"prompt": cleaned_prompt, "temperature": 0.7}, 
            timeout=30)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 成功，响应: {result.get('response', '')[:100]}...")
        else:
            print("✗ 失败")
    except Exception as e:
        print(f"✗ 超时或错误: {e}")

if __name__ == "__main__":
    test_minimal()