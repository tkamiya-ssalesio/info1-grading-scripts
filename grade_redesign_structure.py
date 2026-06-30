#!/usr/bin/env python3
import os
import sys
import json
import re
from html.parser import HTMLParser

class RedesignHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = {
            'h1': 0,
            'h2': 0,
            'h3': 0,
            'ul': 0,
            'ol': 0,
            'li': 0,
            'table': 0,
            'tr': 0,
            'th': 0,
            'td': 0,
            'br': 0
        }
        
    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            self.tags[tag] += 1

def analyze_html(file_path):
    results = {
        'exists': False,
        'has_h1': False,
        'h2_count': 0,
        'has_list': False,
        'li_count': 0,
        'has_table': False,
        'tr_count': 0,
        'th_count': 0,
        'td_count': 0,
        'br_count': 0,
        'errors': []
    }
    
    if not os.path.exists(file_path):
        results['errors'].append("index.html が見つかりません。")
        return results
        
    results['exists'] = True
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        results['errors'].append(f"index.html の読み込み中にエラーが発生しました: {str(e)}")
        return results
        
    parser = RedesignHTMLParser()
    try:
        parser.feed(content)
    except Exception as e:
        results['errors'].append(f"index.html のHTML解析中にエラーが発生しました: {str(e)}")
        return results
        
    results['has_h1'] = parser.tags['h1'] >= 1
    results['h2_count'] = parser.tags['h2'] + parser.tags['h3'] # h3も含めて見出し2以上とする
    results['has_list'] = (parser.tags['ul'] >= 1) or (parser.tags['ol'] >= 1)
    results['li_count'] = parser.tags['li']
    results['has_table'] = parser.tags['table'] >= 1
    results['tr_count'] = parser.tags['tr']
    results['th_count'] = parser.tags['th']
    results['td_count'] = parser.tags['td']
    results['br_count'] = parser.tags['br']
    
    return results

def analyze_chat_history(file_path):
    results = {
        'exists': False,
        'is_valid_json': False,
        'turn_count': 0,
        'user_prompts': [],
        'has_help_seeking': False,
        'found_keywords': [],
        'errors': [],
        'is_markdown_fallback': False
    }
    
    if not os.path.exists(file_path):
        results['errors'].append("copilot-chat-history.json が見つかりません。")
        return results
        
    results['exists'] = True
    
    content = ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        results['errors'].append(f"チャット履歴ファイルの読み込みエラー: {str(e)}")
        return results
        
    try:
        data = json.loads(content)
        results['is_valid_json'] = True
    except json.JSONDecodeError:
        results['is_valid_json'] = False
        results['is_markdown_fallback'] = True
        
        user_lines = []
        for line in content.split('\n'):
            line = line.strip()
            if any(keyword in line for keyword in ["教えて", "どうやって", "エラー", "崩れる", "閉じタグ", "表示されない", "なぜ", "どうして"]):
                user_lines.append(line)
        
        results['turn_count'] = max(1, len(user_lines))
        results['user_prompts'] = user_lines
        
        help_seeking_keywords = ["エラー", "崩れる", "閉じタグ", "表示されない", "理由", "なぜ", "どうして", "間違っ"]
        found = []
        for kw in help_seeking_keywords:
            if kw in content:
                found.append(kw)
        if found:
            results['has_help_seeking'] = True
            results['found_keywords'] = found
            
        results['errors'].append(
            "⚠️ **警告**: ファイルは存在しますが，正しいJSON形式ではありません。\n"
            "VS Codeのチャットメニューから「チャットのエクスポート（Export Chat）」を実行し，"
            "エクスポートされたファイルをそのまま `copilot-chat-history.json` として保存してください。"
        )
        return results

    turns = []
    if isinstance(data, list):
        turns = data
    elif isinstance(data, dict):
        if 'requests' in data:
            turns = data['requests']
        elif 'turns' in data:
            turns = data['turns']
        elif 'history' in data:
            turns = data['history']
            
    user_prompts = []
    for turn in turns:
        if isinstance(turn, dict):
            msg = turn.get('message') or turn.get('prompt')
            if msg:
                if isinstance(msg, dict):
                    text = msg.get('text') or msg.get('content') or ""
                    if text:
                        user_prompts.append(text)
                elif isinstance(msg, str):
                    user_prompts.append(msg)
            elif turn.get('role') == 'user':
                content_text = turn.get('content')
                if content_text:
                    if isinstance(content_text, str):
                        user_prompts.append(content_text)
                    elif isinstance(content_text, list):
                        for item in content_text:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                user_prompts.append(item.get('text', ''))

    results['turn_count'] = len(user_prompts)
    results['user_prompts'] = user_prompts
    
    help_seeking_keywords = ["エラー", "崩れる", "閉じタグ", "表示されない", "理由", "なぜ", "どうして", "間違っ"]
    found_kws = set()
    for prompt in user_prompts:
        for kw in help_seeking_keywords:
            if kw in prompt:
                found_kws.add(kw)
                
    if len(found_kws) >= 1:
        results['has_help_seeking'] = True
        results['found_keywords'] = list(found_kws)
        
    return results

def check_commits():
    commit_msg = os.environ.get('COMMIT_MESSAGE', '')
    return {
        'message': commit_msg,
        'is_standard': 'feat: structure index.html' in commit_msg.lower() or 'structure' in commit_msg.lower() or len(commit_msg) > 0
    }

def main():
    html_res = analyze_html('index.html')
    chat_res = analyze_chat_history('copilot-chat-history.json')
    commit_res = check_commits()
    
    # スコア集計
    score_file = 0
    if html_res['exists']:
        score_file += 1
    if chat_res['exists'] and chat_res['is_valid_json']:
        score_file += 1
        
    score_structure = 0
    if html_res['exists']:
        # 見出し
        if html_res['has_h1'] and html_res['h2_count'] >= 4:
            score_structure += 1
        # リスト
        if html_res['has_list'] and html_res['li_count'] >= 5:
            score_structure += 1
        # テーブル
        if html_res['has_table'] and html_res['tr_count'] >= 5 and html_res['th_count'] >= 3:
            score_structure += 1

    score_chat = 0
    if chat_res['exists']:
        score_chat += 1
        if chat_res['turn_count'] >= 1:
            score_chat += 1
        if chat_res['has_help_seeking']:
            score_chat += 1

    # 総合評価
    total_score = score_file + score_structure + score_chat
    
    if total_score >= 7:
        grade = "🏆 S (素晴らしい！すべての構造化要件を完璧に満たしています)"
    elif total_score >= 5:
        grade = "✅ A (良好です。要件を満たした構造化ができています)"
    elif total_score >= 3:
        grade = "⚠️ B (再提出をおすすめします。未達成の構造化箇所があります)"
    else:
        grade = "❌ C (未完成、または提出ファイルが不足しています)"
        
    report = []
    report.append("# 📝 【自動評価】第5回課題 ルーブリックフィードバック\n")
    report.append(f"現在の総合評価: **{grade}**\n")
    report.append("コミット＆プッシュするたびにこの評価は自動で更新されます。アドバイスを参考に修正してみてください！\n")
    
    report.append("## 📊 ルーブリック達成状況\n")
    report.append("| 評価項目 | 判定 | 状態 | アドバイス / 詳細 |")
    report.append("| :--- | :---: | :--- | :--- |")
    
    # 1. ファイル提出
    files_ok = html_res['exists'] and chat_res['exists'] and chat_res['is_valid_json']
    status_files = "✅ 達成" if files_ok else "⚠️ 要確認"
    detail_files = "必要なファイルが揃っています。"
    if not html_res['exists']:
        detail_files = "`index.html` が見つかりません。"
    elif not chat_res['exists']:
        detail_files = "AIとの対話ログ `copilot-chat-history.json` が提出されていません。"
    elif not chat_res['is_valid_json']:
        detail_files = "`copilot-chat-history.json` が正しいJSON形式ではありません。"
    report.append(f"| **① ファイルの提出** | {'✅' if files_ok else '⚠️'} | {status_files} | {detail_files} |")
    
    # 2. HTML構造化
    html_ok = html_res['exists'] and html_res['has_h1'] and html_res['h2_count'] >= 4 and html_res['has_list'] and html_res['li_count'] >= 5 and html_res['has_table'] and html_res['tr_count'] >= 5
    status_html = "✅ 達成" if html_ok else "⚠️ 未達成あり"
    html_details = []
    if html_res['exists']:
        if not html_res['has_h1']: 
            html_details.append("大見出し(`<h1>`)の不足")
        if html_res['h2_count'] < 4: 
            html_details.append(f"見出し2(`<h2>`)の不足(現在:{html_res['h2_count']}箇所/目標:4箇所)")
        if not html_res['has_list'] or html_res['li_count'] < 5: 
            html_details.append(f"リスト構造が不足(現在項目数:{html_res['li_count']}個/目標:5個)")
        if not html_res['has_table'] or html_res['tr_count'] < 5 or html_res['th_count'] < 3:
            html_details.append("タイムスケジュールの表構造(`<table>`, `tr`, `th`, `td`)の不足・誤り")
    detail_html = "完璧に構造化されています。" if html_ok else "以下の点を確認・追加してください: " + ", ".join(html_details)
    report.append(f"| **② HTMLの構造化** | {'✅' if html_ok else '⚠️'} | {status_html} | {detail_html} |")
    
    # 3. AIのデバッグ活用
    chat_ok = chat_res['exists'] and chat_res['is_valid_json'] and chat_res['turn_count'] >= 1 and chat_res['has_help_seeking']
    status_chat = "✅ 達成" if chat_ok else "⚠️ 要改善"
    chat_details = []
    if chat_res['exists']:
        if not chat_res['is_valid_json']:
            chat_details.append("JSON形式が破損しています")
        else:
            if chat_res['turn_count'] < 1:
                chat_details.append("AIとの対話履歴がありません")
            if not chat_res['has_help_seeking']:
                chat_details.append("AIへの「表示崩れのデバッグ・構文チェック等の質問」が不足しています")
    else:
        chat_details.append("対話履歴ファイル未提出")
    detail_chat = f"AIを適切にデバッグに活用できています。(対話回数: {chat_res['turn_count']}回)" if chat_ok else "改善点: " + ", ".join(chat_details)
    report.append(f"| **③ AIのデバッグ活用** | {'✅' if chat_ok else '⚠️'} | {status_chat} | {detail_chat} |")
    report.append("\n")
    
    # 不要なbrタグのアドバイス（オプショナル）
    if html_res['exists'] and html_res['br_count'] > 5:
        report.append(f"💡 **アドバイス**: `index.html` に `<br>` タグがまだ {html_res['br_count']} 個残っています。\n"
                      "見出し（`h1`, `h2`）やリスト（`li`），表（`tr`）を正しく適用すると，自動的に改行されるため `<br>` は不要になります。余分な `<br>` を削除してみましょう！\n\n")
                      
    if chat_res['errors']:
        report.append("### 📢 ファイル提出に関するエラー/警告\n")
        for err in chat_res['errors']:
            report.append(f"- {err}\n")
        report.append("\n")
        
    report.append("### 💡 コミット＆プッシュの履歴")
    report.append(f"- 今回のコミットメッセージ: `{commit_res['message']}`")
    if commit_res['is_standard']:
        report.append("- ✅ 適切なコミットが行われています。")
    else:
        report.append("- 💡 手順書で推奨されているメッセージ `feat: structure index.html` を使ってコミットすると，より良い履歴になります。")
    report.append("\n")
    
    report.append("### 🎯 次のステップへのアドバイス")
    if grade.startswith("🏆"):
        report.append("完璧です！すべての要件を美しい論理構造でクリアしました。Google Classroomで提出を完了してください。")
    elif grade.startswith("✅"):
        report.append("素晴らしいです！あと一歩で完璧になります。上記の「⚠️ 未達成あり」と書かれた箇所を修正し，再度コミット＆プッシュしてみましょう。")
    else:
        report.append("提出された内容に未達成の箇所が多くあります。手順書(README.md)をよく読み，AIにデバッグを助けてもらいながら，見出し・リスト・表を正しく実装してみましょう。")
        
    with open('feedback.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
        
    print("Grading completed. feedback.md generated.")

if __name__ == '__main__':
    main()
