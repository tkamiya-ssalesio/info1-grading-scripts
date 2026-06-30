#!/usr/bin/env python3
import os
import sys
import json
import re
from html.parser import HTMLParser

class RedesignHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = []
        self.tags = {
            'h1': 0, 'h2': 0, 'h3': 0, 'ul': 0, 'ol': 0, 'li': 0,
            'table': 0, 'tr': 0, 'th': 0, 'td': 0, 'br': 0, 'p': 0
        }
        self.list_stack = []
        self.invalid_p_in_ul = False
        
    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            self.tags[tag] += 1
        
        if tag in ['h1', 'h2', 'h3']:
            self.headings.append(tag)
            
        if tag in ['ul', 'ol']:
            self.list_stack.append(tag)
            
        if tag == 'p' and self.list_stack:
            # ul or ol is active, but a p tag is opened directly inside (invalid structure for list items)
            self.invalid_p_in_ul = True
            
    def handle_endtag(self, tag):
        if tag in ['ul', 'ol'] and self.list_stack:
            self.list_stack.pop()

def analyze_html(file_path):
    results = {
        'exists': False,
        'has_h1': False,
        'headings_order_ok': False,
        'headings': [],
        'has_list': False,
        'li_count': 0,
        'invalid_p_in_ul': False,
        'has_table': False,
        'br_in_td_removed': False,
        'br_count': 0,
        'errors': []
    }
    
    if not os.path.exists(file_path):
        results['errors'].append("index.html が見つかりません．")
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
        
    results['headings'] = parser.headings
    results['has_h1'] = 'h1' in parser.headings
    
    # Check heading order (first heading should be h1, then h2 or h3, no h2 before h1)
    if parser.headings:
        # We expect h1 (main title) to appear before h2 or h3
        try:
            h1_idx = parser.headings.index('h1')
            h2_idx = parser.headings.index('h2') if 'h2' in parser.headings else 999
            if h1_idx < h2_idx:
                results['headings_order_ok'] = True
        except ValueError:
            results['headings_order_ok'] = False
            
    results['has_list'] = (parser.tags['ul'] >= 1) or (parser.tags['ol'] >= 1)
    results['li_count'] = parser.tags['li']
    results['invalid_p_in_ul'] = parser.invalid_p_in_ul
    results['has_table'] = parser.tags['table'] >= 1
    results['br_count'] = parser.tags['br']
    
    # Check if <br> inside tables/td is removed (original had <br><br> in "日時" cell)
    # If the total br_count is <= 1, it means the unnecessary br elements in table are gone.
    if parser.tags['br'] <= 1:
        results['br_in_td_removed'] = True
        
    return results

def get_color_luminance(color_hex):
    # Normalize hex
    color_hex = color_hex.lstrip('#')
    if len(color_hex) == 3:
        color_hex = ''.join([c*2 for c in color_hex])
    if len(color_hex) != 6:
        return 0.0
        
    r = int(color_hex[0:2], 16) / 255.0
    g = int(color_hex[2:4], 16) / 255.0
    b = int(color_hex[4:6], 16) / 255.0
    
    values = []
    for c in [r, g, b]:
        if c <= 0.03928:
            values.append(c / 12.92)
        else:
            values.append(((c + 0.055) / 1.055) ** 2.4)
            
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]

def get_contrast_ratio(c1, c2):
    try:
        l1 = get_color_luminance(c1)
        l2 = get_color_luminance(c2)
        if l1 < l2:
            l1, l2 = l2, l1
        return (l1 + 0.05) / (l2 + 0.05)
    except Exception:
        return 1.0

def analyze_css(file_path):
    results = {
        'exists': False,
        'halations_resolved': True,
        'color_count': 0,
        'unique_colors': [],
        'contrast_ok': True,
        'font_family_ok': False,
        'line_height_ok': False,
        'table_padding_ok': False,
        'whitespace_ok': False,
        'cud_ok': False,
        'errors': []
    }
    
    if not os.path.exists(file_path):
        results['errors'].append("style.css が見つかりません．")
        return results
        
    results['exists'] = True
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        results['errors'].append(f"style.css の読み込み中にエラーが発生しました: {str(e)}")
        return results
        
    # Check for original bad combinations (halation: green background #00ff00 and red text #ff0000)
    # Also check if they are still using raw bright green and red.
    has_lime_bg = re.search(r'background-color\s*:\s*(#00ff00|lime|#0f0|rgb\(\s*0\s*,\s*255\s*,\s*0\s*\))', content, re.I)
    has_red_text = re.search(r'color\s*:\s*(#ff0000|red|#f00|rgb\(\s*255\s*,\s*0\s*,\s*0\s*\))', content, re.I)
    if has_lime_bg and has_red_text:
        results['halations_resolved'] = False
        
    # Find all hex colors
    hex_colors = set(re.findall(r'#([0-9a-fA-F]{3,6})', content))
    # Filter valid hex sizes
    valid_colors = []
    for hc in hex_colors:
        if len(hc) in [3, 6]:
            valid_colors.append('#' + hc.lower())
    results['unique_colors'] = list(set(valid_colors))
    results['color_count'] = len(results['unique_colors'])
    
    # Simple check for sans-serif (Japanese gothic is usually sans-serif)
    if 'sans-serif' in content.lower() or 'gothic' in content.lower() or 'ゴシック' in content:
        results['font_family_ok'] = True
        
    # Check for line-height fix (must not be line-height: 1.0 or similar tight line heights)
    lh_matches = re.findall(r'line-height\s*:\s*([0-9.]+)', content)
    results['line_height_ok'] = True
    for lh in lh_matches:
        try:
            val = float(lh)
            if val <= 1.2:
                results['line_height_ok'] = False
        except ValueError:
            pass
            
    # Check for th, td padding (should not be empty or 0)
    has_padding = re.search(r'(td|th|table)[^{]*\{[^}]*padding\s*:\s*([^;}]+)', content, re.I)
    if has_padding:
        padding_val = has_padding.group(2).strip()
        if padding_val not in ['0', '0px', 'none']:
            results['table_padding_ok'] = True
            
    # Check for margin/padding usage indicating whitespace design
    margin_matches = re.findall(r'margin\s*:\s*([^;}]+)', content)
    padding_matches = re.findall(r'padding\s*:\s*([^;}]+)', content)
    if len(margin_matches) >= 2 or len(padding_matches) >= 2:
        results['whitespace_ok'] = True
        
    # Check for CUD style indicators (border, bold, background-color differences, or text-decoration on warning blocks)
    # The warning block in index.html is class="alert-message"
    alert_style = re.search(r'\.alert-message\s*\{[^}]*\}', content, re.S)
    if alert_style:
        style_body = alert_style.group(0)
        # Should have border, padding, background-color, or font-weight
        if 'border' in style_body or 'padding' in style_body or 'background' in style_body or 'font-weight' in style_body:
            results['cud_ok'] = True
            
    # Estimate contrast ratio from typical background & text pairings in CSS
    # If the user changed the color of body or elements, ensure it is high enough
    # If they use dark body color (like #333, #222) and light background (white, #fff), it is OK.
    results['contrast_ok'] = True
    body_bg = '#ffffff'
    body_fg = '#000000'
    
    # Try parsing body bg and color
    body_style = re.search(r'body\s*\{[^}]*\}', content, re.S)
    if body_style:
        b_body = body_style.group(0)
        bg_match = re.search(r'background-color\s*:\s*(#[0-9a-fA-F]{3,6})', b_body, re.I)
        fg_match = re.search(r'color\s*:\s*(#[0-9a-fA-F]{3,6})', b_body, re.I)
        if bg_match:
            body_bg = bg_match.group(1)
        if fg_match:
            body_fg = fg_match.group(1)
            
    contrast = get_contrast_ratio(body_bg, body_fg)
    if contrast < 4.5:
        # If user changed background to a problematic low contrast value
        results['contrast_ok'] = False
        
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
        results['errors'].append("copilot-chat-history.json が見つかりません．")
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
            if any(keyword in line for keyword in ["教えて", "どうやって", "エラー", "ハレーション", "コントラスト", "余白", "崩れる", "なぜ", "どうして"]):
                user_lines.append(line)
        
        results['turn_count'] = max(1, len(user_lines))
        results['user_prompts'] = user_lines
        
        help_seeking_keywords = ["ハレーション", "コントラスト", "余白", "見づらい", "エラー", "崩れる", "理由", "なぜ", "どうして", "間違っ"]
        found = []
        for kw in help_seeking_keywords:
            if kw in content:
                found.append(kw)
        if found:
            results['has_help_seeking'] = True
            results['found_keywords'] = found
            
        results['errors'].append(
            "⚠️ **警告**: ファイルは存在しますが，正しいJSON形式ではありません．\n"
            "VS Codeのチャットメニューから「チャットのエクスポート（Export Chat）」を実行し，"
            "エクスポートされたファイルをそのまま `copilot-chat-history.json` として保存してください．"
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
    
    help_seeking_keywords = ["ハレーション", "コントラスト", "余白", "見づらい", "エラー", "崩れる", "理由", "なぜ", "どうして", "間違っ"]
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
        'is_standard': 'feat: style index.html' in commit_msg.lower() or 'style' in commit_msg.lower() or len(commit_msg) > 0
    }

def main():
    html_res = analyze_html('index.html')
    css_res = analyze_css('style.css')
    chat_res = analyze_chat_history('copilot-chat-history.json')
    commit_res = check_commits()
    
    # スコア集計
    score_file = 0
    if html_res['exists']:
        score_file += 1
    if css_res['exists']:
        score_file += 1
    if chat_res['exists'] and chat_res['is_valid_json']:
        score_file += 1
        
    score_visual = 0
    if css_res['exists']:
        # ハレーションの解消
        if css_res['halations_resolved']:
            score_visual += 1
        # 配色4色ルール
        if css_res['color_count'] <= 4:
            score_visual += 1
        # 適切な行間とフォント
        if css_res['font_family_ok'] and css_res['line_height_ok']:
            score_visual += 1
        # 余白の設定（テーブル余白・マージン）
        if css_res['table_padding_ok'] and css_res['whitespace_ok']:
            score_visual += 1
        # カラーユニバーサルデザイン（CUD）
        if css_res['cud_ok']:
            score_visual += 1

    score_html_fix = 0
    if html_res['exists']:
        # 見出し階層の修正
        if html_res['has_h1'] and html_res['headings_order_ok']:
            score_html_fix += 1
        # リストエラーの修正
        if not html_res['invalid_p_in_ul']:
            score_html_fix += 1
        # テーブル内brタグの修正
        if html_res['br_in_td_removed']:
            score_html_fix += 1

    score_chat = 0
    if chat_res['exists']:
        score_chat += 1
        if chat_res['turn_count'] >= 1:
            score_chat += 1
        if chat_res['has_help_seeking']:
            score_chat += 1

    # 総合評価（満点: 3 (ファイル) + 5 (CSS) + 3 (HTML修正) + 3 (AI対話) = 14点）
    total_score = score_file + score_visual + score_html_fix + score_chat
    
    if total_score >= 12:
        grade = "🏆 S (素晴らしい！すべてのビジュアルリデザインと構造修正を完璧に満たしています)"
    elif total_score >= 8:
        grade = "✅ A (良好です．情報デザインの原則を満たした表現ができています)"
    elif total_score >= 5:
        grade = "⚠️ B (再提出をおすすめします．未達成のビジュアル・構造化の警告箇所があります)"
    else:
        grade = "❌ C (未完成，または提出ファイルが不足しています)"
        
    report = []
    report.append("# 📝 【自動評価】第6回課題 ルーブリックフィードバック\n")
    report.append(f"現在の総合評価: **{grade}**\n")
    report.append("コミット＆プッシュするたびにこの評価は自動で更新されます．アドバイスを参考に修正してみてください！\n")
    
    report.append("## 📊 ルーブリック達成状況\n")
    report.append("| 評価項目 | 判定 | 状態 | アドバイス / 詳細 |")
    report.append("| :--- | :---: | :--- | :--- |")
    
    # 1. ファイル提出
    files_ok = html_res['exists'] and css_res['exists'] and chat_res['exists'] and chat_res['is_valid_json']
    status_files = "✅ 達成" if files_ok else "⚠️ 要確認"
    detail_files = "必要なファイルがすべて揃っています．"
    if not html_res['exists']:
        detail_files = "`index.html` が見つかりません．"
    elif not css_res['exists']:
        detail_files = "`style.css` が見つかりません．"
    elif not chat_res['exists']:
        detail_files = "AIとの対話ログ `copilot-chat-history.json` が提出されていません．"
    elif not chat_res['is_valid_json']:
        detail_files = "`copilot-chat-history.json` が正しいJSON形式ではありません（警告マークが表示されています）．"
    report.append(f"| ① 提出ファイル確認 | {status_files} | 3点中 {score_file}点 | {detail_files} |")
    
    # 2. HTML構造デバッグ
    html_ok = (html_res['has_h1'] and html_res['headings_order_ok'] and 
               not html_res['invalid_p_in_ul'] and html_res['br_in_td_removed'])
    status_html = "✅ 達成" if html_ok else "🔴 要修正"
    detail_html = []
    if not html_res.get('has_h1', False):
        detail_html.append("大見出し（第12回 聖サレジオ学園ビブリオバトル大会...）に `<h1>` タグが適用されていません．")
    elif not html_res.get('headings_order_ok', False):
        detail_html.append("見出しの階層（`h1` ➔ `h2` ➔ `h3`）の順序が逆転したままです．")
    if html_res.get('invalid_p_in_ul', False):
        detail_html.append("リストタグ（`<ul>`）の中に `<li>` ではない `<p>` タグが混入しています．")
    if not html_res.get('br_in_td_removed', False):
        detail_html.append("開催日時の表セルの中に，無駄な改行（`<br><br>`）が残っています．CSSの余白（padding）を使って間隔をあけましょう．")
    if not detail_html:
        detail_html = ["HTMLの構造的エラーはすべて綺麗に修正されています！"]
    report.append(f"| ② HTML構造の修正 | {status_html} | 3点中 {score_html_fix}点 | {'<br>'.join(detail_html)} |")
    
    # 3. CSSビジュアルデザイン
    css_ok = (css_res['halations_resolved'] and css_res['color_count'] <= 4 and 
              css_res['font_family_ok'] and css_res['line_height_ok'] and 
              css_res['table_padding_ok'] and css_res['whitespace_ok'] and css_res['cud_ok'])
    status_css = "✅ 達成" if css_ok else "🔴 要修正"
    detail_css = []
    if not css_res.get('halations_resolved', True):
        detail_css.append("蛍光グリーンの背景と赤い文字のハレーション（補色かつ高彩度）が解消されていません．目が疲れない配色に変更してください．")
    if css_res.get('color_count', 0) > 4:
        detail_css.append(f"使用している色が多すぎます（検出された色コード数: {css_res['color_count']}）．4色以内（背景・文字・メイン・強調）に整理しましょう．")
    if not css_res.get('font_family_ok', False):
        detail_css.append("画面上で読みやすいゴシック体（`sans-serif` など）が指定されていません．")
    if not css_res.get('line_height_ok', True):
        detail_css.append("行間（`line-height`）が狭すぎて，文字が潰れて重なり合っています．`line-height: 1.6` 程度に広げてください．")
    if not css_res.get('table_padding_ok', False):
        detail_css.append("テーブルのセル内に余白（`padding`）が指定されておらず，罫線に文字が張り付いて窮屈です．")
    if not css_res.get('whitespace_ok', False):
        detail_css.append("見出しやグループ間の余白（`margin`）が不足しており，すべての情報が隙間なく詰まって見えます．")
    if not css_res.get('cud_ok', False):
        detail_css.append("注意事項（`.alert-message`）が色（赤など）だけで強調されています．色覚多様性に配慮し，太字（`font-weight: bold`）や枠線，絵文字等を併用してください．")
    if not detail_css:
        detail_css = ["すべての情報デザインビジュアル原則を満たしています！素晴らしいレスキューです！"]
    report.append(f"| ③ CSSビジュアル設計 | {status_css} | 5点中 {score_visual}点 | {'<br>'.join(detail_css)} |")
    
    # 4. AIチャット
    chat_ok = chat_res['exists'] and chat_res['turn_count'] >= 1 and chat_res['has_help_seeking']
    status_chat = "✅ 達成" if chat_ok else "⚠️ 要確認"
    detail_chat = []
    if not chat_res['exists']:
        detail_chat.append("チャット履歴がありません．")
    else:
        detail_chat.append(f"AIとの対話回数: {chat_res['turn_count']}回")
        if not chat_res['has_help_seeking']:
            detail_chat.append("デザインやエラーについての具体的なHelp-seeking（相談・デバッグ）の様子が確認できませんでした．")
        else:
            detail_chat.append(f"相談キーワード検出: {', '.join(chat_res['found_keywords'])}")
    report.append(f"| ④ AIとの共同デバッグ | {status_chat} | 3点中 {score_chat}点 | {'<br>'.join(detail_chat)} |")
    
    # 5. コミットメッセージ
    commit_ok = commit_res['is_standard']
    status_commit = "✅ 達成" if commit_ok else "⚠️ 推奨"
    detail_commit = f"実際のコミットメッセージ: `{commit_res['message']}`"
    if not commit_ok:
        detail_commit += " (推奨: `feat: style index.html` を含むメッセージ)"
    report.append(f"| ⑤ コミットルール | {status_commit} | - | {detail_commit} |")
    
    report.append("\n## 💡 アドバイス・ヒント\n")
    report.append("1. **ハレーションを避ける**: 背景は白や薄いグレー（`#ffffff` や `#f8f9fa`），文字は濃いグレー（`#333333`）にすると，コントラストがはっきりしつつ目も疲れません．\n")
    report.append("2. **余白を持たせる**: グループ同士を離すには `margin-bottom: 24px` のようにマージンをあけ，テーブルのセルを見やすくするには `th, td { padding: 12px; }` を適用すると劇的に変わります．\n")
    report.append("3. **CUDの実現**: `.alert-message { font-weight: bold; border-left: 4px solid #d32f2f; padding-left: 10px; }` のように，左線や太字をあてることで，色に頼らずとも警告であることが一目でわかります．\n")

    # 成果レポート出力
    with open('feedback.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
        
    print("Grading completed. Report written to feedback.md")
    
    # SまたはA評価で終了ステータス0, それ以外（不合格）なら終了ステータス1とする（ActionsでのIssue更新判定のため）
    if total_score >= 8:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
