import json

# 打开并读取 JSON 文件
with open('gmgn/gmgn.json', 'r') as f:
    data = json.load(f)

follows = data['data']['followings']
# 现在 data 是一个 Python 字典


with open('gmgn/ray.txt', 'w', encoding='utf-8') as f:
    for item in follows:
        f.write(f"{item['address']} {item['name']}\n")

with open('gmgn/xxyy.txt', 'w', encoding='utf-8') as f:
    for item in follows:
        f.write(f"{item['address']},{item['name']},车头,\n")