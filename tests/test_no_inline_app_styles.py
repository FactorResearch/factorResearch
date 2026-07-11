from pathlib import Path


def test_app_modules_do_not_use_inline_style_props():
    app_modules = Path(__file__).parents[1] / "codes" / "app_modules"
    offenders = [
        path
        for path in app_modules.rglob("*.py")
        if "style=" in path.read_text()
    ]

    assert offenders == []
