#!/usr/bin/env python3
import os
import sys
import json
import re
from html.parser import HTMLParser

class RubricHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = {
            'h1': 0,
            'h2': 0,
            'p': 0,
            'ul': 0,
            'ol': 0,
            'li': 0
        }
        
    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            self.tags[tag] += 1

def analyze_html(file_path):
    results = {
        'exists': False,
        'has_h1': False,
        'has_h2': False,
        'has_p': False,
        'has_list': False,
        'li_count': 0,
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
        
    parser = RubricHTMLParser()
    try:
        parser.feed(content)
    except Exception as e:
        results['errors'].append(f"index.html のHTML解析中にエラーが発生しました: {str(e)}")
        return results
        
    results['has_h1'] = parser.tags['h1'] >= 1
    results['has_h2'] = parser.tags['h2'] >= 1
    results['has_p'] = parser.tags['p'] >= 1
    results['has_list'] = (parser.tags['ul'] >= 1) or (parser.tags['ol'] >= 1)
    results['li_count'] = parser.tags['li']
    
    return results

def analyze_css(file_path):
    results = {
        'exists': False,
        'has_bg_color': False,
        'bg_color_changed': False,
        'has_color': False,
        'has_font_size': False,
        'has_spacing': False,
        'errors': []
    }
    
    if not os.path.exists(file_path):
        results['errors'].append("style.css が見つかりません。")
        return results
        
    results['exists'] = True
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        results['errors'].append(f"style.css の読み込み中にエラーが発生しました: {str(e)}")
        return results
        
    # 各種キーワード・指定を検出
    results['has_bg_color'] = 'background-color' in content
    results['has_color'] = 'color' in content and 'background-color' not in content.replace('background-color', '') # 単なるcolor指定があるか
    # background-color以外の箇所の'color'を簡易チェック
    color_matches = re.findall(r'(?<!background-)\bcolor\b', content)
    results['has_color'] = len(color_matches) >= 1
    
    results['has_font_size'] = 'font-size' in content
    results['has_spacing'] = 'padding' in content or 'margin' in content
    
    # 背景色が初期値（白）以外に変更されているかチェック
    bg_match = re.search(r'background-color\s*:\s*([^;}\s]+)', content)
    if bg_match:
        bg_val = bg_match.group(1).lower().strip()
        # 白を表す代表的な指定値を除外
        white_values = ['white', '#fff', '#ffffff', 'rgb(255,255,255)', 'rgba(255,255,255,1)', '#ffffffff']
        if bg_val not in white_values:
            results['bg_color_changed'] = True
            
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
        
    # JSONとしてパースを試みる
    try:
        data = json.loads(content)
        results['is_valid_json'] = True
    except json.JSONDecodeError:
        # JSONパース失敗時のフォールバック処理
        results['is_valid_json'] = False
        # Markdown等で保存されている可能性をチェック
        # 簡単な正規表現で、生徒の発話と思われる箇所を抽出
        # 例：ユーザーの発言を「user:」や「あなた:」や行頭のプロンプトから簡易推測
        results['is_markdown_fallback'] = True
        
        # テキストベースで簡易分析
        # ユーザーの発言ターン数を大雑把に数える
        # 改行で区切って、質問らしい行（？や問、教えて、など）や特定のパターンを数える
        user_lines = []
        for line in content.split('\n'):
            line = line.strip()
            # 簡易キーワードで行を抽出
            if any(keyword in line for keyword in ["教えて", "どうやって", "意味", "なぜ", "どうして", "作成して", "追加して", "やり方"]):
                user_lines.append(line)
        
        results['turn_count'] = max(1, len(user_lines)) # 最低1ターンは何か書いてあるとみなす
        results['user_prompts'] = user_lines
        
        # キーワード検出
        help_seeking_keywords = ["意味", "説明", "なぜ", "どうして", "どういう", "解説", "理由", "詳しく", "とは"]
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
            "エクスポートされたファイルをそのまま `copilot-chat-history.json` として保存してください。\n"
            "(テキストのコピペや手動保存の場合，JSON形式が壊れることがあります)"
        )
        return results

    # JSON構造の探索
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
            # 1. VS Code standard structure: message property
            msg = turn.get('message') or turn.get('prompt')
            if msg:
                if isinstance(msg, dict):
                    text = msg.get('text') or msg.get('content') or ""
                    if text:
                        user_prompts.append(text)
                elif isinstance(msg, str):
                    user_prompts.append(msg)
            # 2. Alternative role/content structure
            elif turn.get('role') == 'user':
                content_text = turn.get('content')
                if content_text:
                    if isinstance(content_text, str):
                        user_prompts.append(content_text)
                    elif isinstance(content_text, list):
                        # メッセージが構造化リストの場合
                        for item in content_text:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                user_prompts.append(item.get('text', ''))

    results['turn_count'] = len(user_prompts)
    results['user_prompts'] = user_prompts
    
    # 能動的ヘルプシーキングの判定 (説明を求めるキーワードが含まれるか)
    help_seeking_keywords = ["意味", "説明", "なぜ", "どうして", "どういう", "解説", "理由", "詳しく", "とは"]
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
    # 本来はGitのコミットメッセージを検証するが、
    # Actions上で実行する場合は環境変数等から取得。
    # ここではシンプルにプッシュが実行されているのでコミット履歴はあると仮定し、
    # ワークフロー側でコミットメッセージを取得して環境変数から渡す形にする。
    commit_msg = os.environ.get('COMMIT_MESSAGE', '')
    return {
        'message': commit_msg,
        'is_standard': 'setup environment and ai chat' in commit_msg.lower() or 'setup' in commit_msg.lower() or len(commit_msg) > 0
    }

def main():
    html_res = analyze_html('index.html')
    css_res = analyze_css('style.css')
    chat_res = analyze_chat_history('copilot-chat-history.json')
    commit_res = check_commits()
    
    # ルーブリック採点ロジック
    # S: すべての要件を満たし，AI対話も良好
    # A: HTML/CSSは達成，AI対話に一部不足あり
    # B: HTML/CSSに一部未達成あり，またはチャット履歴の提出不備
    # C: ほぼ未着手
    
    score_html = 0
    if html_res['exists']:
        score_html += 1
        if html_res['has_h1'] and html_res['has_h2'] and html_res['has_p']:
            score_html += 1
        if html_res['has_list'] and html_res['li_count'] >= 3:
            score_html += 1
            
    score_css = 0
    if css_res['exists']:
        score_css += 1
        if css_res['has_bg_color'] and css_res['bg_color_changed']:
            score_css += 1
        if css_res['has_color'] and css_res['has_font_size'] and css_res['has_spacing']:
            score_css += 1
            
    score_chat = 0
    if chat_res['exists']:
        score_chat += 1
        if chat_res['is_valid_json']:
            score_chat += 1
        if chat_res['turn_count'] >= 2:
            score_chat += 1
        if chat_res['has_help_seeking']:
            score_chat += 1

    # 総合評価の判定
    total_requirements = 11 # 最大ポイント
    current_points = score_html + score_css + score_chat
    
    if current_points >= 10:
        grade = "🏆 S (素晴らしい！すべての要件をクリアしています)"
    elif current_points >= 8:
        grade = "✅ A (良好です。一部の調整でさらに良くなります)"
    elif current_points >= 5:
        grade = "⚠️ B (再提出をおすすめします。要件に未達成の部分があります)"
    else:
        grade = "❌ C (未完成、または提出ファイルが不足しています)"
        
    # レポート作成
    report = []
    report.append("# 📝 【自動評価】第4回課題 ルーブリックフィードバック\n")
    report.append(f"現在の総合評価: **{grade}**\n")
    report.append("コミット＆プッシュするたびにこの評価は自動で更新されます。アドバイスを参考に修正してみてください！\n")
    
    # 評価テーブル
    report.append("## 📊 ルーブリック達成状況\n")
    report.append("| 評価項目 | 判定 | 状態 | アドバイス / 詳細 |")
    report.append("| :--- | :---: | :--- | :--- |")
    
    # 1. 提出ファイル
    files_ok = html_res['exists'] and css_res['exists'] and chat_res['exists'] and chat_res['is_valid_json']
    status_files = "✅ 達成" if files_ok else "⚠️ 要確認"
    detail_files = "必要なファイルがすべて正しい形式で揃っています。"
    if not html_res['exists']:
        detail_files = "`index.html` が見つかりません。"
    elif not css_res['exists']:
        detail_files = "`style.css` が見つかりません。"
    elif not chat_res['exists']:
        detail_files = "AIとの対話ログ `copilot-chat-history.json` が提出されていません。"
    elif not chat_res['is_valid_json']:
        detail_files = "`copilot-chat-history.json` が正しいJSON形式ではありません。"
    report.append(f"| **① ファイルの提出** | {'✅' if files_ok else '⚠️'} | {status_files} | {detail_files} |")
    
    # 2. HTML構造
    html_ok = html_res['has_h1'] and html_res['has_h2'] and html_res['has_p'] and html_res['has_list'] and html_res['li_count'] >= 3
    status_html = "✅ 達成" if html_ok else "⚠️ 未達成あり"
    html_details = []
    if not html_res['has_h1']: html_details.append("見出し1(`<h1>`)の不足")
    if not html_res['has_h2']: html_details.append("見出し2(`<h2>`)の不足")
    if not html_res['has_p']: html_details.append("自己紹介の段落(`<p>`)の不足")
    if not html_res['has_list'] or html_res['li_count'] < 3: 
        html_details.append(f"リスト項目が不足(現在:{html_res['li_count']}個/目標:3個以上)")
    detail_html = "HTMLの構造化要件を満たしています。" if html_ok else "以下のタグを追加してください: " + ", ".join(html_details)
    report.append(f"| **② 自己紹介のHTML (構造化)** | {'✅' if html_ok else '⚠️'} | {status_html} | {detail_html} |")
    
    # 3. CSS装飾
    css_ok = css_res['has_bg_color'] and css_res['bg_color_changed'] and css_res['has_color'] and css_res['has_font_size'] and css_res['has_spacing']
    status_css = "✅ 達成" if css_ok else "⚠️ 未達成あり"
    css_details = []
    if not css_res['has_bg_color'] or not css_res['bg_color_changed']: css_details.append("背景色の変更(白以外)")
    if not css_res['has_color']: css_details.append("文字色の変更(`color`)")
    if not css_res['has_font_size']: css_details.append("フォントサイズの調整(`font-size`)")
    if not css_res['has_spacing']: css_details.append("余白の設定(`padding`または`margin`)")
    detail_css = "CSSの装飾要件を満たしています。" if css_ok else "以下のスタイル設定を追加してください: " + ", ".join(css_details)
    report.append(f"| **③ 自己紹介のCSS (装飾)** | {'✅' if css_ok else '⚠️'} | {status_css} | {detail_css} |")
    
    # 4. AIの活用
    chat_ok = chat_res['exists'] and chat_res['is_valid_json'] and chat_res['turn_count'] >= 2 and chat_res['has_help_seeking']
    status_chat = "✅ 達成" if chat_ok else "⚠️ 要改善"
    chat_details = []
    if chat_res['exists']:
        if not chat_res['is_valid_json']:
            chat_details.append("JSON形式が破損")
        else:
            if chat_res['turn_count'] < 2:
                chat_details.append(f"対話回数が不足(現在:{chat_res['turn_count']}回/目標:2往復以上)")
            if not chat_res['has_help_seeking']:
                chat_details.append("AIへの「コードの仕組みや意味を説明させる質問」が不足")
    else:
        chat_details.append("対話履歴ファイル未提出")
    
    detail_chat = f"AIを適切に活用できています。(対話回数: {chat_res['turn_count']}回)" if chat_ok else "改善点: " + ", ".join(chat_details)
    report.append(f"| **④ AIの活用プロセス** | {'✅' if chat_ok else '⚠️'} | {status_chat} | {detail_chat} |")
    report.append("\n")
    
    # フォールバック発生時の警告や個別アドバイス
    if chat_res['errors']:
        report.append("### 📢 ファイル提出に関するエラー/警告\n")
        for err in chat_res['errors']:
            report.append(f"- {err}\n")
        report.append("\n")
        
    # コミット履歴のアドバイス
    report.append("### 💡 コミット＆プッシュの履歴")
    report.append(f"- 今回のコミットメッセージ: `{commit_res['message']}`")
    if commit_res['is_standard']:
        report.append("- ✅ 適切なコミットが行われています。")
    else:
        report.append("- 💡 手順書で推奨されているメッセージ `setup environment and ai chat` を使ってコミットすると，より良い履歴になります。")
    report.append("\n")
    
    # アシスタントからの総評アドバイス
    report.append("### 🎯 次のステップへのアドバイス")
    if grade.startswith("🏆"):
        report.append("完璧です！すべての要件を素晴らしい品質でクリアしました。Google Classroomで提出を完了してください。")
    elif grade.startswith("✅"):
        report.append("あと一歩で完璧です！上記の「⚠️ 未達成あり」または「⚠️ 要改善」と書かれた箇所を修正し，再度コミット＆プッシュしてみましょう。")
    else:
        report.append("提出された内容に不足している箇所が多くあります。手順書(README.md)をよく読み，AIと相談しながら一つずつ要件を満たしていきましょう。")
        
    # feedback.md に出力
    with open('feedback.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
        
    print("Grading completed. feedback.md generated.")

if __name__ == '__main__':
    main()
