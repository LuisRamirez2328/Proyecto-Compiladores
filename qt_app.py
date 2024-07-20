import sys
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, QDockWidget, QTreeWidget, 
                             QAction, QVBoxLayout, QMenuBar, QToolBar, QStatusBar, QFileDialog, 
                             QTreeWidgetItem, QTabWidget, QWidget, QTextEdit, QCompleter)
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor, QPainter, QIcon, QTextCursor

class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlighting_rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(Qt.darkBlue)
        keyword_format.setFontWeight(QFont.Bold)

        keywords = ["inicio", "fin", "funcion", "retornar", "var", "mientras", "si", "entonces", "fin_si", "sino", "para", "imprimir"]
        for word in keywords:
            pattern = re.compile(f"\\b{word}\\b")
            rule = (pattern, keyword_format)
            self._highlighting_rules.append(rule)

        string_format = QTextCharFormat()
        string_format.setForeground(Qt.darkGreen)
        self._highlighting_rules.append((re.compile(r'"[^"]*"'), string_format))

        error_format = QTextCharFormat()
        error_format.setForeground(Qt.red)
        self._error_format = error_format

    def highlightBlock(self, text):
        for pattern, format in self._highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format)

    def highlightError(self, start, end):
        self.setFormat(start, end - start, self._error_format)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    updateRequest = pyqtSignal(QRect, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Courier", 10))
        self.highlighter = SyntaxHighlighter(self.document())
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)

        keywords = ["inicio", "fin", "funcion", "retornar", "var", "mientras", "si", "entonces", "fin_si", "sino", "para", "imprimir"]
        self.completer = QCompleter(keywords, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompleter(self.completer)

    def lineNumberAreaWidth(self):
        digits = 1
        max_ = max(1, self.blockCount())
        while max_ >= 10:
            max_ //= 10
            digits += 1
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def highlightCurrentLine(self):
        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.lightGray)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, top, self.lineNumberArea.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def setCompleter(self, completer):
        completer.setWidget(self)
        completer.activated.connect(self.insertCompletion)
        self.completer = completer

    def insertCompletion(self, completion):
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def focusInEvent(self, event):
        if self.completer:
            self.completer.setWidget(self)
        super().focusInEvent(event)

    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        isShortcut = (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_E)
        if not self.completer or not isShortcut:
            super().keyPressEvent(event)

        ctrlOrShift = event.modifiers() in (Qt.ControlModifier, Qt.ShiftModifier)
        if not self.completer or (ctrlOrShift and len(event.text()) == 0):
            return

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="  # End of word
        hasModifier = (event.modifiers() != Qt.NoModifier) and not ctrlOrShift
        completionPrefix = self.textUnderCursor()

        if not isShortcut and (hasModifier or len(event.text()) == 0 or len(completionPrefix) < 1 or event.text()[-1] in eow):
            self.completer.popup().hide()
            return

        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analizador de Lenguaje")
        self.setGeometry(100, 100, 1000, 800)

        # Editor de código
        self.code_editor = CodeEditor()
        self.setCentralWidget(self.code_editor)

        # Árbol de sintaxis
        self.syntax_tree = QTreeWidget()
        self.syntax_tree.setHeaderLabels(["Árbol de Sintaxis"])
        dock_tree = QDockWidget("Árbol de Sintaxis")
        dock_tree.setWidget(self.syntax_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_tree)

        # Consola de salida
        self.output_console = QPlainTextEdit()
        self.output_console.setReadOnly(True)
        dock_console = QDockWidget("Consola de Salida")
        dock_console.setWidget(self.output_console)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_console)

        # Menú
        self.create_menu()

        # Barra de herramientas
        self.create_toolbar()

        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Estado inicial del tema
        self.dark_mode = False

    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('Archivo')
        open_action = QAction('Abrir', self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_action = QAction('Guardar', self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        edit_menu = menubar.addMenu('Editar')
        analyze_menu = menubar.addMenu('Analizar')

        analyze_action = QAction('Analizar', self)
        analyze_action.triggered.connect(self.analyze_code)
        analyze_menu.addAction(analyze_action)

        view_menu = menubar.addMenu('Vista')
        toggle_theme_action = QAction('Toggle Dark/Light Mode', self)
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)

    def create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        open_action = QAction(QIcon("static/open.png"), 'Abrir', self)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)

        save_action = QAction(QIcon("static/save.png"), 'Guardar', self)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)

        run_action = QAction(QIcon("static/flecha.png"), 'Run', self)  # Reemplaza con la ruta a tu ícono
        run_action.triggered.connect(self.run_code)
        toolbar.addAction(run_action)

        analyze_action = QAction(QIcon("static/analyze.png"), 'Analizar', self)  # Reemplaza con la ruta a tu ícono
        analyze_action.triggered.connect(self.analyze_code)
        toolbar.addAction(analyze_action)

    def open_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Abrir Archivo", "", 
                                                   "Archivos de Texto (*.txt);;Todos los Archivos (*)", 
                                                   options=options)
        if file_name:
            with open(file_name, 'r') as file:
                self.code_editor.setPlainText(file.read())

    def save_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Guardar Archivo", "", 
                                                   "Archivos de Texto (*.txt);;Todos los Archivos (*)", 
                                                   options=options)
        if file_name:
            with open(file_name, 'w') as file:
                file.write(self.code_editor.toPlainText())

    def run_code(self):
        code = self.code_editor.toPlainText()
        lines = code.split('\n')
        variables = {}
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("var"):
                var_name, var_value = line[len("var"):].split('=')
                var_name = var_name.strip()
                var_value = var_value.strip()
                try:
                    variables[var_name] = int(var_value)
                except ValueError:
                    self.output_console.appendPlainText(f'Error: valor inválido para la variable {var_name}')
                    return
            elif line.startswith("imprimir"):
                message = line[len("imprimir"):].strip()
                if message in variables:
                    self.output_console.appendPlainText(str(variables[message]))
                else:
                    self.output_console.appendPlainText(message)
            elif line.startswith("si"):
                condition = line[len("si"):].strip().split("entonces")[0].strip()
                if "==" in condition:
                    var_name, value = condition.split("==")
                    var_name = var_name.strip()
                    value = value.strip()
                    i += 1
                    if variables.get(var_name) == int(value):
                        while i < len(lines) and not lines[i].strip().startswith("fin_si"):
                            inner_line = lines[i].strip()
                            if inner_line.startswith("imprimir"):
                                message = inner_line[len("imprimir"):].strip()
                                if message in variables:
                                    self.output_console.appendPlainText(str(variables[message]))
                                else:
                                    self.output_console.appendPlainText(message)
                            i += 1
            i += 1

    def analyze_code(self):
        code = self.code_editor.toPlainText()
        
        # Análisis léxico
        tokens = self.lexer(code)
        if tokens is None:
            self.status_bar.showMessage("Error léxico", 2000)
            return
        
        # Análisis sintáctico
        parse_tree = self.parser(tokens)
        if parse_tree is None:
            self.status_bar.showMessage("Error sintáctico", 2000)
            return
        
        # Análisis semántico
        semantic_ok = self.semantic_analyzer(parse_tree)
        if not semantic_ok:
            self.status_bar.showMessage("Error semántico", 2000)
            return
        
        # Mostrar resultados
        self.output_console.appendPlainText("Análisis completado exitosamente")
        self.status_bar.showMessage("Análisis completado", 2000)
        
        # Mostrar árbol de sintaxis
        self.display_syntax_tree(parse_tree)
        
    def lexer(self, code):
        keywords = {"inicio", "fin", "funcion", "retornar", "var", "mientras", "si", "entonces", "fin_si", "sino", "para", "imprimir"}
        token_specification = [
            ('STRING',  r'"[^"]*"'),       # String literal
            ('NUMBER',  r'\d+'),           # Integer or decimal number
            ('ID',      r'[A-Za-z_]\w*'),  # Identifiers
            ('OP',      r'[+\-*/=]'),      # Arithmetic and assignment operators
            ('NEWLINE', r'\n'),            # Line endings
            ('SKIP',    r'[ \t]+'),        # Skip over spaces and tabs
            ('MISMATCH',r'.'),             # Any other character
        ]
        tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in token_specification)
        get_token = re.compile(tok_regex).match
        line_num = 1
        line_start = 0
        tokens = []
        mo = get_token(code)
        while mo is not None:
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'NEWLINE':
                line_start = mo.end()
                line_num += 1
            elif kind == 'SKIP':
                pass
            elif kind == 'MISMATCH':
                self.output_console.appendPlainText(f'Error léxico: {value} inesperado en la línea {line_num}')
                return None
            else:
                if kind == 'ID' and value in keywords:
                    kind = value.upper()
                tokens.append((kind, value))
            mo = get_token(code, mo.end())
        return tokens

    def parser(self, tokens):
        if not tokens or tokens[0][0] != 'INICIO' or tokens[-1][0] != 'FIN':
            self.output_console.appendPlainText('Error sintáctico: el código debe comenzar con "inicio" y terminar con "fin".')
            return None
        
        i = 0
        parse_tree = QTreeWidgetItem(["inicio"])
        current_node = parse_tree
        while i < len(tokens):
            kind, value = tokens[i]
            if kind == 'IMPRIMIR':
                if i + 1 >= len(tokens) or tokens[i + 1][0] not in {'ID', 'NUMBER', 'STRING'}:
                    self.output_console.appendPlainText(f'Error sintáctico: se esperaba un identificador, número o cadena después de "imprimir" en la posición {i}')
                    return None
                node = QTreeWidgetItem([f'imprimir {tokens[i + 1][1]}'])
                current_node.addChild(node)
                i += 1
            elif kind == 'SI':
                if i + 1 >= len(tokens) or tokens[i + 1][0] not in {'ID', 'NUMBER'}:
                    self.output_console.appendPlainText(f'Error sintáctico: se esperaba una condición después de "si" en la posición {i}')
                    return None
                if i + 2 >= len(tokens) or tokens[i + 2][0] != 'ENTONCES':
                    self.output_console.appendPlainText(f'Error sintáctico: se esperaba "entonces" en la posición {i + 2}')
                    return None
                condition_node = QTreeWidgetItem([f'si {tokens[i + 1][1]} == {tokens[i + 3][1]} entonces'])
                current_node.addChild(condition_node)
                current_node = condition_node
                i += 2
                while i < len(tokens) and tokens[i][0] != 'FIN_SI':
                    kind, value = tokens[i]
                    if kind == 'IMPRIMIR':
                        node = QTreeWidgetItem([f'imprimir {tokens[i + 1][1]}'])
                        current_node.addChild(node)
                    i += 1
                if i >= len(tokens) or tokens[i][0] != 'FIN_SI':
                    self.output_console.appendPlainText(f'Error sintáctico: se esperaba "fin_si"')
                    return None
                current_node = parse_tree
            i += 1
        return parse_tree

    def semantic_analyzer(self, parse_tree):
        # Un análisis semántico más complejo debería recorrer el árbol de análisis y comprobar la coherencia semántica.
        # Aquí simplemente devolvemos True para simplificar.
        return True

    def display_syntax_tree(self, parse_tree):
        self.syntax_tree.clear()
        self.syntax_tree.addTopLevelItem(parse_tree)

    def toggle_theme(self):
        if self.dark_mode:
            self.set_light_theme()
        else:
            self.set_dark_theme()
        self.dark_mode = not self.dark_mode

    def set_dark_theme(self):
        dark_palette = self.palette()
        dark_palette.setColor(self.backgroundRole(), QColor(53, 53, 53))
        dark_palette.setColor(self.foregroundRole(), Qt.white)
        self.setPalette(dark_palette)

        self.code_editor.setStyleSheet("background-color: #2b2b2b; color: #ffffff;")
        self.output_console.setStyleSheet("background-color: #2b2b2b; color: #ffffff;")

    def set_light_theme(self):
        light_palette = self.palette()
        light_palette.setColor(self.backgroundRole(), Qt.white)
        light_palette.setColor(self.foregroundRole(), Qt.black)
        self.setPalette(light_palette)

        self.code_editor.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.output_console.setStyleSheet("background-color: #ffffff; color: #000000;")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
