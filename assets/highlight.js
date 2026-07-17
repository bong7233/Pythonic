/* highlight.js — 의존성 없는 소형 구문 강조기
 * 지원: python, js, ts, bash, json, yaml, cpp, sql, text
 * 사용: HL.highlight(code, lang) -> HTML 문자열
 */
(function (global) {
  'use strict';

  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  var PY_KW = 'False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield';
  var PY_SOFT = 'match|case|type';
  var PY_BUILTIN = 'abs|aiter|anext|all|any|ascii|bin|bool|breakpoint|bytearray|bytes|callable|chr|classmethod|compile|complex|delattr|dict|dir|divmod|enumerate|eval|exec|filter|float|format|frozenset|getattr|globals|hasattr|hash|help|hex|id|input|int|isinstance|issubclass|iter|len|list|locals|map|max|memoryview|min|next|object|oct|open|ord|pow|print|property|range|repr|reversed|round|set|setattr|slice|sorted|staticmethod|str|sum|super|tuple|vars|zip|__import__';
  var PY_SELF = 'self|cls|NotImplemented|Ellipsis|__name__|__main__|__file__|__doc__';
  var PY_EXC = 'BaseException|Exception|ArithmeticError|AssertionError|AttributeError|BlockingIOError|BrokenPipeError|BufferError|BytesWarning|ChildProcessError|ConnectionError|ConnectionAbortedError|ConnectionRefusedError|ConnectionResetError|DeprecationWarning|EOFError|EnvironmentError|FileExistsError|FileNotFoundError|FloatingPointError|FutureWarning|GeneratorExit|IOError|ImportError|ImportWarning|IndentationError|IndexError|InterruptedError|IsADirectoryError|KeyError|KeyboardInterrupt|LookupError|MemoryError|ModuleNotFoundError|NameError|NotADirectoryError|NotImplementedError|OSError|OverflowError|PendingDeprecationWarning|PermissionError|ProcessLookupError|RecursionError|ReferenceError|ResourceWarning|RuntimeError|RuntimeWarning|StopAsyncIteration|StopIteration|SyntaxError|SyntaxWarning|SystemError|SystemExit|TabError|TimeoutError|TypeError|UnboundLocalError|UnicodeDecodeError|UnicodeEncodeError|UnicodeError|UnicodeTranslateError|UnicodeWarning|UserWarning|ValueError|Warning|ZeroDivisionError|ExceptionGroup|BaseExceptionGroup';

  var RULES = {};

  RULES.python = [
    [/^#[^\n]*/, 'c'],
    // triple-quoted (접두사 포함)
    [/^(?:[rRbBuUfF]{0,3})(?:"""[\s\S]*?"""|'''[\s\S]*?''')/, 's'],
    // single-line strings
    [/^(?:[rRbBuUfF]{0,3})(?:"(?:\\[\s\S]|[^"\\\n])*"|'(?:\\[\s\S]|[^'\\\n])*')/, 's'],
    [/^@[A-Za-z_][\w.]*/, 'd'],
    [/^(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|(?:\d[\d_]*)?\.\d[\d_]*(?:[eE][+-]?\d+)?[jJ]?|\d[\d_]*\.?(?:[eE][+-]?\d+)?[jJ]?)\b/, 'n'],
    [new RegExp('^(?:' + PY_KW + ')\\b'), 'k'],
    [new RegExp('^(?:' + PY_SOFT + ')(?=\\s+[\\w\\[({"\'-])'), 'k'],
    [new RegExp('^(?:' + PY_EXC + ')\\b'), 't'],
    [new RegExp('^(?:' + PY_SELF + ')\\b'), 'v'],
    [new RegExp('^(?:' + PY_BUILTIN + ')\\b'), 'b'],
    [/^[A-Z]\w*(?=[\s.,)\]:=]|$)/, 't'],
    [/^[A-Za-z_]\w*(?=\s*\()/, 'f'],
    [/^[A-Za-z_]\w*/, null],
    [/^\s+/, null],
    [/^[^\w\s]/, 'o']
  ];

  var JS_KW = 'await|async|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|function|if|import|in|instanceof|let|new|of|return|static|super|switch|this|throw|try|typeof|var|void|while|with|yield|from|as|get|set';
  RULES.js = [
    [/^\/\/[^\n]*/, 'c'],
    [/^\/\*[\s\S]*?\*\//, 'c'],
    [/^`(?:\\[\s\S]|[^`\\])*`/, 's'],
    [/^"(?:\\[\s\S]|[^"\\\n])*"|^'(?:\\[\s\S]|[^'\\\n])*'/, 's'],
    [/^(?:0[xX][0-9a-fA-F_]+|\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?n?)\b/, 'n'],
    [new RegExp('^(?:' + JS_KW + ')\\b'), 'k'],
    [/^(?:true|false|null|undefined|NaN|Infinity)\b/, 'b'],
    [/^(?:console|document|window|Math|JSON|Object|Array|String|Number|Boolean|Promise|Map|Set|Symbol|RegExp|Date|Error)\b/, 't'],
    [/^[A-Za-z_$][\w$]*(?=\s*\()/, 'f'],
    [/^[A-Za-z_$][\w$]*/, null],
    [/^\s+/, null],
    [/^[^\w\s$]/, 'o']
  ];
  RULES.ts = RULES.js;
  RULES.javascript = RULES.js;

  RULES.bash = [
    [/^#[^\n]*/, 'c'],
    [/^"(?:\\[\s\S]|[^"\\])*"|^'[^']*'/, 's'],
    [/^\$\{[^}]*\}|^\$[A-Za-z_]\w*|^\$\d/, 'v'],
    [/^(?:^|(?<=\s))-{1,2}[A-Za-z][\w-]*/, 'd'],
    [/^\b(?:if|then|else|elif|fi|for|while|do|done|case|esac|function|return|in|export|local|source|set|echo|cd|exit)\b/, 'k'],
    [/^\b(?:python|python3|pip|pip3|uv|uvx|ruff|mypy|pytest|git|docker|conda|apt|apt-get|sudo|colcon|ros2|rosdep|npm|node|curl|wget|make|cmake|source|nvidia-smi)\b/, 'f'],
    [/^\b\d+\b/, 'n'],
    [/^[A-Za-z_][\w-]*/, null],
    [/^\s+/, null],
    [/^[^\w\s]/, 'o']
  ];
  RULES.sh = RULES.bash;
  RULES.shell = RULES.bash;
  RULES.console = RULES.bash;

  RULES.json = [
    [/^"(?:\\[\s\S]|[^"\\])*"(?=\s*:)/, 'a'],
    [/^"(?:\\[\s\S]|[^"\\])*"/, 's'],
    [/^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/, 'n'],
    [/^\b(?:true|false|null)\b/, 'b'],
    [/^\s+/, null],
    [/^[^\s]/, 'o']
  ];

  RULES.yaml = [
    [/^#[^\n]*/, 'c'],
    [/^(?:^|(?<=\n))\s*[-\w.$/]+(?=\s*:)/, 'a'],
    [/^"(?:\\[\s\S]|[^"\\])*"|^'[^']*'/, 's'],
    [/^\b(?:true|false|null|yes|no|on|off|~)\b/, 'b'],
    [/^-?\d+(?:\.\d+)?\b/, 'n'],
    [/^[\w.\/-]+/, null],
    [/^\s+/, null],
    [/^[^\w\s]/, 'o']
  ];

  var CPP_KW = 'alignas|alignof|and|asm|auto|bool|break|case|catch|char|class|concept|const|consteval|constexpr|constinit|const_cast|continue|co_await|co_return|co_yield|decltype|default|delete|do|double|dynamic_cast|else|enum|explicit|export|extern|false|float|for|friend|goto|if|inline|int|long|mutable|namespace|new|noexcept|nullptr|operator|or|private|protected|public|register|reinterpret_cast|requires|return|short|signed|sizeof|static|static_assert|static_cast|struct|switch|template|this|thread_local|throw|true|try|typedef|typeid|typename|union|unsigned|using|virtual|void|volatile|while';
  RULES.cpp = [
    [/^\/\/[^\n]*/, 'c'],
    [/^\/\*[\s\S]*?\*\//, 'c'],
    [/^#\s*\w+/, 'd'],
    [/^"(?:\\[\s\S]|[^"\\\n])*"|^'(?:\\[\s\S]|[^'\\\n])*'/, 's'],
    [/^(?:0[xX][0-9a-fA-F']+|\d[\d']*\.?\d*(?:[eE][+-]?\d+)?[fFuUlL]*)\b/, 'n'],
    [new RegExp('^(?:' + CPP_KW + ')\\b'), 'k'],
    [/^std\b/, 'b'],
    [/^[A-Za-z_]\w*(?=\s*[<(])/, 'f'],
    [/^[A-Za-z_]\w*/, null],
    [/^\s+/, null],
    [/^[^\w\s]/, 'o']
  ];
  RULES.c = RULES.cpp;

  RULES.sql = [
    [/^--[^\n]*/, 'c'],
    [/^'(?:''|[^'])*'/, 's'],
    [/^\b\d+(?:\.\d+)?\b/, 'n'],
    [/^\b(?:SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|INDEX|DROP|ALTER|AND|OR|NOT|NULL|AS|DISTINCT|UNION|ALL|CASE|WHEN|THEN|ELSE|END|WITH|PRIMARY|KEY|FOREIGN|REFERENCES)\b/i, 'k'],
    [/^[A-Za-z_]\w*/, null],
    [/^\s+/, null],
    [/^[^\w\s]/, 'o']
  ];

  var ALIASES = {
    py: 'python', python3: 'python', pycon: 'python', ipython: 'python',
    'c++': 'cpp', cxx: 'cpp', yml: 'yaml', zsh: 'bash', jsonc: 'json'
  };

  function tokenize(code, rules) {
    var out = '';
    var pos = 0;
    var guard = 0;
    while (pos < code.length && guard++ < 500000) {
      var rest = code.slice(pos);
      var matched = false;
      for (var i = 0; i < rules.length; i++) {
        var m = rules[i][0].exec(rest);
        if (m && m[0].length > 0) {
          var cls = rules[i][1];
          var text = esc(m[0]);
          out += cls ? '<span class="hl-' + cls + '">' + text + '</span>' : text;
          pos += m[0].length;
          matched = true;
          break;
        }
      }
      if (!matched) {
        out += esc(code[pos]);
        pos++;
      }
    }
    return out;
  }

  // 대화형 세션(>>> / $)은 프롬프트와 출력을 구분해서 칠한다.
  function highlightRepl(code) {
    return code.split('\n').map(function (line) {
      var m = /^(\s*)(>>>|\.\.\.)(\s?)([\s\S]*)$/.exec(line);
      if (m) {
        return m[1] + '<span class="hl-prompt">' + m[2] + '</span>' + m[3] +
          tokenize(m[4], RULES.python);
      }
      if (line.trim() === '') return '';
      return '<span class="hl-out">' + esc(line) + '</span>';
    }).join('\n');
  }

  function highlight(code, lang) {
    lang = (lang || '').toLowerCase().trim();
    lang = ALIASES[lang] || lang;
    if (lang === 'repl' || lang === 'pyrepl') return highlightRepl(code);
    var rules = RULES[lang];
    if (!rules) return esc(code);
    return tokenize(code, rules);
  }

  global.HL = { highlight: highlight, escape: esc, languages: Object.keys(RULES) };
})(this);
