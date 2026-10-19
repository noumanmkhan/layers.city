"""The dark theme for the site's generated pages (guides, venues), the same palette the hand-written pages use:
it follows the phone's or computer's setting, or the choice saved on the map (Auto, Light, Dark; localStorage
'theme', the same origin). Fact sheets stay light: they are made to print."""

# Before any style: a saved Light or Dark choice wins over the system setting.
SCRIPT = ("<script>try { const t = localStorage.getItem('theme'); if (t === 'light' || t === 'dark') "
          "document.documentElement.dataset.theme = t; } catch (e) {}</script>")

TOKENS = ('--bg:#15171B;--card:#1E2126;--ink:#ECEDEF;--ink-2:#C3C6CC;--ink-3:#9AA0A8;--muted:#8A8F97;--rule:#373B42;'
          '--accent:#E5364F;--accent-soft:rgba(229,54,79,.16);--soft:rgba(229,54,79,.16);--grid:rgba(236,237,239,.045);'
          '--land:#24272D;--street:#3A3E45;--go:#5FB98A')


def css(rules=()):
    """The dark block: the tokens, and any rules for colours the tokens don't reach, under both selectors."""
    A, B = ':root:not([data-theme="light"])', ':root[data-theme="dark"]'
    media = '@media (prefers-color-scheme: dark){' + A + '{color-scheme:dark;' + TOKENS + '}' + ''.join(f' {A} {r}' for r in rules) + '}'
    forced = B + '{color-scheme:dark;' + TOKENS + '}' + ''.join(f'\n{B} {r}' for r in rules)
    return '\n' + media + '\n' + forced
