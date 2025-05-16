import json

with open('gmgn/cielo.json', 'r') as f:
    data = json.load(f)

with open('gmgn/cielo.txt', 'w', encoding='utf-8') as f:
    for item in data:
        f.write(f"{item['wallet']}:{item['label']},\n")
