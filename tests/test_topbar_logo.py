from codes.app_modules.layout import _topbar


def test_topbar_uses_the_theme_safe_svg_logo():
    logo = _topbar().children[0].children[0]

    assert logo.src == "/assets/logo.svg"
    assert logo.alt == "Research Factor"
