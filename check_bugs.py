# -*- coding: utf-8 -*-
"""
اسکریپت چک خودکار باگ‌های ربات
--------------------------------
این فایل رو کنار main.py (تو همون پوشه‌ی بات) بذار و اجرا کن:

    python check_bugs.py

چیکار می‌کنه:
  ۱. همه‌ی فایل‌های .py پوشه رو از نظر خطای نحوی (Syntax Error) چک می‌کنه.
  ۲. هر فایل رو واقعاً import می‌کنه تا خطاهای «این تابع/متغیر وجود نداره»
     که موقع اجرا لو می‌رن رو زودتر پیدا کنه.
  ۳. اگه کتابخونه‌ی python-telegram-bot نصب باشه، همه‌ی جاهایی که
     context.bot.XXX(...) یا update.effective_chat.bot.XXX(...) صدا زده
     شده رو با متدهای واقعی کلاس Bot مقایسه می‌کنه و اگه متدی وجود
     نداشته باشه (مثل همون get_chat_history که قبلاً پیدا کردیم) گزارش می‌ده.

چیکار نمی‌کنه (مهم):
  - منطق کد رو نمی‌فهمه. باگ‌هایی مثل ترتیب اشتباه handlerها یا شرط
    اشتباه رو پیدا نمی‌کنه — چون از نظر نحوی درستن، فقط رفتارشون غلطه.
  - چیزی رو خودش اصلاح نمی‌کنه، فقط گزارش می‌ده.
"""

import ast
import importlib.util
import os
import sys
import py_compile


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# فایل‌هایی که import کردنشون ممکنه واقعاً به تلگرام/سرور وصل بشه یا
# نیاز به توکن واقعی داشته باشه، بهتره فقط از نظر نحوی چک بشن نه import.
SKIP_IMPORT_CHECK = {"main.py"}


def find_python_files():
    files = []
    for name in os.listdir(PROJECT_DIR):
        if name.endswith(".py") and name != os.path.basename(__file__):
            files.append(name)
    return sorted(files)


def check_syntax(filename):
    """چک خطای نحوی با py_compile"""
    path = os.path.join(PROJECT_DIR, filename)
    try:
        py_compile.compile(path, doraise=True)
        return None
    except py_compile.PyCompileError as e:
        return str(e)


def check_import(filename):
    """سعی می‌کنه فایل رو import کنه تا خطاهای زمان بارگذاری رو پیدا کنه"""
    if filename in SKIP_IMPORT_CHECK:
        return None
    module_name = filename[:-3]
    path = os.path.join(PROJECT_DIR, filename)
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def check_bot_methods(filename):
    """
    چک می‌کنه که متدهای context.bot.XXX / bot.XXX واقعاً روی
    کلاس Bot از python-telegram-bot وجود داشته باشن.
    """
    try:
        from telegram import Bot
    except ImportError:
        return ["⚠️  کتابخونه‌ی python-telegram-bot نصب نیست — این بخش از چک رد شد."]

    valid_methods = set(dir(Bot))
    path = os.path.join(PROJECT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []  # قبلاً تو check_syntax گزارش شده

    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func
            # دنبال الگوی ...bot.METHOD(...) می‌گردیم
            if isinstance(attr.value, ast.Attribute) and attr.value.attr == "bot":
                method_name = attr.attr
                if method_name not in valid_methods and not method_name.startswith("_"):
                    problems.append(
                        f"خط {node.lineno}: `bot.{method_name}(...)` — "
                        f"همچین متدی روی کلاس Bot وجود نداره."
                    )
            elif isinstance(attr.value, ast.Name) and attr.value.id == "bot":
                method_name = attr.attr
                if method_name not in valid_methods and not method_name.startswith("_"):
                    problems.append(
                        f"خط {node.lineno}: `bot.{method_name}(...)` — "
                        f"همچین متدی روی کلاس Bot وجود نداره."
                    )
    return problems


def main():
    files = find_python_files()
    if not files:
        print("هیچ فایل .py ای تو این پوشه پیدا نشد.")
        return

    total_issues = 0
    print(f"در حال بررسی {len(files)} فایل...\n")

    for filename in files:
        file_issues = []

        syntax_error = check_syntax(filename)
        if syntax_error:
            file_issues.append(f"❌ خطای نحوی:\n   {syntax_error}")

        if not syntax_error:
            import_error = check_import(filename)
            if import_error:
                file_issues.append(f"❌ خطای import/اجرا:\n   {import_error}")

            bot_method_issues = check_bot_methods(filename)
            for issue in bot_method_issues:
                if issue.startswith("⚠️"):
                    continue
                file_issues.append(f"❌ متد نامعتبر: {issue}")

        if file_issues:
            print(f"📄 {filename}")
            for issue in file_issues:
                print(f"   {issue}")
            print()
            total_issues += len(file_issues)

    print("=" * 40)
    if total_issues == 0:
        print("✅ هیچ مشکل قابل‌تشخیصی پیدا نشد.")
        print("   (یادت باشه: باگ‌های منطقی رو این اسکریپت تشخیص نمی‌ده)")
    else:
        print(f"⚠️  در مجموع {total_issues} مشکل پیدا شد.")


if __name__ == "__main__":
    main()
