import re

file_path = r"api_service\core\llm_diagnosis.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换 create_user_prompt 调用为极简版本
old_pattern = r'''        user_prompt = create_user_prompt\(
            classification_result=classification_dict,
           <arg_key>description</arg_key><arg_value>Create fix script file
