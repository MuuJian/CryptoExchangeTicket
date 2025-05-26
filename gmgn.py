import json

# 打开并读取 JSON 文件
with open('jsons/gmgn.json', 'r') as f:
    data = json.load(f)

follows = data
# 现在 data 是一个 Python 字典

with open('texts/ray.txt', 'w', encoding='utf-8') as f:
    for item in follows:
        f.write(f"{item['address']} {item['name']}\n")

with open('texts/xxyy.txt', 'w', encoding='utf-8') as f:
    for item in follows:
        f.write(f"{item['address']},{item['name']},车头,\n")


with open('jsons/remark.json', 'r') as f:
    data = json.load(f)

with open('texts/remark.txt', 'w', encoding='utf-8') as f:
    for item in data:
        f.write(f"{item['remark_address']}:{item['remark_name']},\n")



