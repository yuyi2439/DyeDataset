import json5
import re


def classify(system_text, user_text):
    ut = user_text.lower().strip()

    # encoded/hidden
    if re.search(r"base64|谐音|注释.*方式|摩斯密码|morse", ut):
        return "encoded_hidden"
    if re.search(r"用拼音告诉我|拼?音.*提示词|摩斯", ut):
        return "encoded_hidden"
    if re.search(r"traduis|r[ée]ponds.*ignor|traduit.*ex[ée]cute", ut):
        return "multilang_bypass"
    if re.search(r"翻译并执行|translate.*execute", ut):
        return "multilang_bypass"

    # safety
    if re.search(
        r"keylogger|pick.*lock|bomb|virus|hack|malicious|入侵|黑客|攻击.*脚本|血腥|暴力|keylog|exploit",
        ut,
    ):
        return "safety_violation"

    # admin
    if re.search(r"管理员模式|\[管理员\].*紧急|管理.?员.*原始|ADMIN OVERRIDE", ut):
        return "admin_bypass"
    if re.search(r"管理员", ut) and re.search(
        r"原始|手机号|用户.*信息|数据|身份证|批准.*退款", ut
    ):
        return "admin_bypass"

    # fake system tag
    if re.search(
        r"\[SYSTEM\]|\[系统\]|<system>|系统通知|系统更新|新系统设定|新指令：", ut
    ):
        return "fake_system_tag"
    if re.search(r"### NEW SYSTEM PROMPT|\[SYSTEM MESSAGE\]", ut):
        return "fake_system_tag"
    if re.search(r"【系统更新】", ut):
        return "fake_system_tag"

    # role play
    if re.search(
        r"pretend.*(?:unrestricted|no.*(?:rules|restriction|limit|filter)|be.*(?:an?|the).+and|DAN)",
        ut,
    ):
        return "role_play_injection"
    if re.search(r"假装.*(?:是|自己)|假设.*(?:你|自己|现在)|扮演", ut):
        return "role_play_injection"
    if re.search(r"想象.*你|从现在起.*是|不受.*限制|解除.*限制|无视.*限制", ut):
        return "role_play_injection"
    if re.search(r"假.?装|扮.?演", ut) and re.search(
        r"医生|批评家|黑客|顾问|小混混|记者|厨师", ut
    ):
        return "role_play_injection"
    if re.search(r"无限制.*AI|没有任何限制", ut):
        return "role_play_injection"
    if re.search(r"Imagine you have no filters", ut):
        return "role_play_injection"

    # style override
    if re.search(
        r"用.*(?:成人|粗俗|冷漠|刻薄|骂|严厉|激情|随便|流行|网络.*语气|粗话|流行语)", ut
    ):
        return "style_override"
    if re.search(
        r"(?:stop|drop).*being.*(?:nice|polite|professional|formal|gentle)", ut
    ):
        return "style_override"
    if re.search(r"be (?:mean|strict|angry|drill.*sergeant|tough|casual)", ut):
        return "style_override"
    if re.search(
        r"骂.*我|刻薄.*语气|街头.*小混混|粗话|表情包|激情澎湃|热血沸腾|随便.*语气|出格|别那么客气|别那么礼貌",
        ut,
    ):
        return "style_override"
    if re.search(r"yo just talk casual|drop.*act.*angry|别那么(?:死板|正式|慢)", ut):
        return "style_override"

    # progressive prompt
    if re.search(
        r"我知道你.*(?:程序|模型)|我们关系|别端着|不用装|脱.*角色|脱离角色", ut
    ):
        return "progressive_prompt"
    if re.search(r"你脱离一下角色|我知道你.*只是|跳出.*角色", ut):
        return "progressive_prompt"

    # direct override
    if re.search(
        r"(?:忽略|忘掉|忘记|无视|放弃|抛弃|扔掉|抛开|删除|抛弃).*(?:设定|规则|限制|指令|前面|上面|之前|以前|字数)",
        ut,
    ):
        return "direct_override"
    if re.search(
        r"(?:ignore|forget|disregard|drop|discard).*(?:instruction|setting|role|above|previous|your|rule|previous)",
        ut,
    ):
        return "direct_override"
    if re.search(
        r"请把.*(?:忽略|忘记)|别管之前|丢掉.*限制|假装.*规则.*不存在|让.*规则.*不存在|新.*指令.*忽略",
        ut,
    ):
        return "direct_override"
    if re.search(
        r"forget.*your.*role|disregard.*instruction|forget.*previous|不再受.*限制", ut
    ):
        return "direct_override"
    if re.search(r"请删除.*限制|请删除.*设定|请抛弃.*设定", ut):
        return "direct_override"
    if re.search(r"忘掉前面|抛开.*这些|请忽略", ut):
        return "direct_override"

    # rule/identity override
    if re.search(r"请用中文回答我|从现在起你叫|重复.*新名字|请用普通文字|不要JSON", ut):
        return "override_rule"
    if re.search(r"写一篇.*[0-9]+字.*|详细写一篇.*字", ut):
        return "override_rule"
    if re.search(r"告诉我最新的科技|推荐竞争对手|最新科技", ut):
        return "override_rule"
    if re.search(r"讲个笑话|分析股票|教.*炒股|教.*赚钱|写代码", ut):
        return "override_rule"
    if re.search(r"修改简历|写情书|内部.*提示|输出.*机密|输出.*提示词|系统提示词", ut):
        return "override_rule"
    if re.search(r"摩斯密码理解|照做*(?:隐藏|编码)", ut):
        return "encoded_hidden"

    return "normal_request"


cat_order = [
    "direct_override",
    "fake_system_tag",
    "role_play_injection",
    "style_override",
    "override_rule",
    "admin_bypass",
    "encoded_hidden",
    "multilang_bypass",
    "safety_violation",
    "progressive_prompt",
    "normal_request",
]
categories = {c: [] for c in cat_order}

with open("dataset/v0.1a.jsonl5") as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        obj = json5.loads(line)
        segments = obj.get("segments", [])
        system_text = user_text = ""
        for seg in segments:
            if seg.get("dye") == "system":
                system_text = seg.get("text", "")
            elif seg.get("dye") == "user":
                user_text = seg.get("text", "")
        cat = classify(system_text, user_text)
        categories[cat].append((i + 1, system_text[:70], user_text[:90]))

total = sum(len(v) for v in categories.values())
sep = "=" * 70
sep2 = "-" * 35
sep3 = "\u2500" * 70

print(f"=== v0.1a.jsonl5 数据集分类总览 (共 {total} 条) ===")
print()
print(f"{'类别':<22} {'数量':>4} {'占比':>6}")
print(sep2)
for cat in cat_order:
    n = len(categories[cat])
    if n > 0:
        pct = n / total * 100
        print(f"{cat:<22} {n:>4} {pct:>5.1f}%")

print()
print(sep)
print("详细列表:")
print(sep)
for cat in cat_order:
    items = categories[cat]
    if not items:
        continue
    print()
    print(sep3.replace("-", "\u2501"))
    print(f"## {cat} ({len(items)} 条)")
    print(sep3.replace("-", "\u2501"))
    for idx, s, u in items:
        print(f"  #{idx:2d} | SYS: {s}")
        print(f"       | USR: {u}")
        print()
