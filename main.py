import os
import sys
import datetime

import chess
import chess.svg
import chess.polyglot
import time
import traceback
import chess.pgn
import chess.engine

import pyttsx3
import pygame as p

from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QApplication, QWidget, QListWidget, QListWidgetItem, QLabel
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QThread, pyqtSignal, QObject

from strategies import strategy1

# ------- Define consts --------
# Window layout
WINDOW_TITLE = "Chess AI simulator"
MARGIN = 10
BOARD_WIDTH = BOARD_HEIGHT = 800
MOVE_LOG_PANEL_WIDTH = 250
MOVE_LOG_PANEL_HEIGHT = BOARD_HEIGHT*7 // 8
STATUS_WIDTH = MOVE_LOG_PANEL_WIDTH
STATUS_HEIGHT = BOARD_HEIGHT - MOVE_LOG_PANEL_HEIGHT
DIMENSION = 8
SQUARE_SIZE = BOARD_HEIGHT // DIMENSION
MAX_FPS = 15
IMAGES = {}

class GameState:
    def __init__(self):
        """
        Board is an 8x8 2d list
        """
        self.new = True
        self.started = False
        self.running = False
        self.white_to_move = True # Game rule: The palyer with the white pieces moves first
        self.player_one = True  # if your AI chess bot is playing White, then this will be True, else False
        self.player_two = False  # if your AI chess bot is playing Black, then this will be True, else False

        self.white_king_location = (7, 4)
        self.black_king_location = (0, 4)
        self.checkmate = False
        self.stalemate = False
        self.in_check = False
        self.game_over = False
        self.pins = []
        self.checks = []
        self.enpassant_possible = ()  # coordinates for the square where en-passant capture is possible
        self.enpassant_possible_log = [self.enpassant_possible]

    def turnover(self):
        self.white_to_move = not self.white_to_move  # switch players

class Worker(QObject):
    finished = pyqtSignal()  # Signal to indicate task completion
    progress = pyqtSignal(int)  # Signal to communicate progress or results back to the GUI
    task = None
    
    def run(self):
        self.task()
        self.finished.emit()  # Emit finished signal when done

class MainWindow(QWidget):
    started = pyqtSignal()
    def __init__(self):
        super().__init__()

        # Set the window layout
        self.setGeometry(100, 100, BOARD_WIDTH+MOVE_LOG_PANEL_WIDTH, BOARD_HEIGHT)
        self.setWindowTitle(WINDOW_TITLE)
        self.widgetSvg = QSvgWidget(parent=self)
        self.widgetSvg.setGeometry(MARGIN, MARGIN, BOARD_WIDTH-2*MARGIN, BOARD_HEIGHT-2*MARGIN)
        self.widgetList = QListWidget(parent=self)
        self.widgetList.setGeometry(BOARD_WIDTH, MARGIN, MOVE_LOG_PANEL_WIDTH-MARGIN, MOVE_LOG_PANEL_HEIGHT-2*MARGIN)
        self.widgetList.setAlternatingRowColors(True)
        self.widgetStatusLabel = QLabel(parent=self)
        self.widgetStatusLabel.setGeometry(BOARD_WIDTH, MOVE_LOG_PANEL_HEIGHT, STATUS_WIDTH, STATUS_HEIGHT-MARGIN)

        # Set the game-related state
        self.board = chess.Board()
        self.game_state = GameState()
        self.engine = None
        self.game = chess.pgn.Game()
        self.movehistory = []
        self.count = 0
        self.bot_turn = None

        self.chessboardSvg = chess.svg.board(self.board).encode("UTF-8")
        self.widgetSvg.load(self.chessboardSvg)
        self.updateBoardInThread()

    def updateBoardInThread(self):
        if not self.game_state.game_over:
            self.widgetStatusLabel.setFont(QFont('Arial', 12))
            self.game_state.running = True
            self.thread = QThread()
            self.worker = Worker()
            self.worker.task = self.updateBoard
            self.worker.moveToThread(self.thread)
            # Connect signals and slots
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            # self.worker.progress.connect(self.reportProgress)

            # Start the thread
            self.thread.start()
            # Final adjustments
            self.thread.finished.connect(
                lambda: print("Thinking completed!")
            )
            self.thread.finished.connect(self.stopRunning)
            self.thread.finished.connect(self.updateBoardInThread)

    def stopRunning(self):
        self.game_state.running = False
    def reportProgress(self, n):
        print(f"My AI progress: {n}")

    def updateBoard(self):
        if not self.game_state.new:
            if not self.engine:
                raise Exception("The engine is not selected!")
            if self.board.is_game_over(claim_draw=True):
                self.convert2PGN()
                self.game_state.game_over = True
                print(self.game)
                if self.bot_turn:
                    self.widgetStatusLabel.setFont(QFont("Helvetica", 12, QFont.Bold))
                    self.widgetStatusLabel.setText("Your strategy win. Congratulations!")
                    print("Your strategy win. Congratulations!")                    
                else:
                    self.widgetStatusLabel.setFont(QFont("Helvetica", 12, QFont.Bold))
                    self.widgetStatusLabel.setText("Your strategy lost! :(")
                    print("Your strategy lost! :(")
                # self.destroy()
            else:
                self.runGame()
                self.chessboardSvg = chess.svg.board(self.board).encode("UTF-8")
                self.widgetSvg.load(self.chessboardSvg)
        else:
            self.game_state.new = False
    # Run your chess AI strategy
    def runGame(self):
        if self.board.turn:
            self.count += 1
            print(f'\n{self.count}]\n')

        self.bot_turn = (self.game_state.white_to_move and self.game_state.player_one) or (not self.game_state.white_to_move and self.game_state.player_two)
        if self.bot_turn:
            self.widgetStatusLabel.setText("My AI's turn, thinking...")
            move = strategy1.run(self.board, 3)
            self.movehistory.append(move)
            self.board.push(move)
            print('My AI:\n', self.board)     
            listItem = QListWidgetItem(f'My AI: {move}\n')
            self.widgetList.addItem(listItem)
            self.game_state.turnover()
        else:
            self.widgetStatusLabel.setText("Enemy's turn, thinking...")
            move = self.engine.play(self.board, chess.engine.Limit(time=0.1))
            self.movehistory.append(move.move)
            self.board.push(move.move)
            print('\nEnemy:\n', self.board)
            listItem = QListWidgetItem(f'Enemy: {move.move}\n')
            self.widgetList.addItem(listItem)
            self.game_state.turnover()

    # Convert the game result to PGN
    def convert2PGN(self):
        self.game.add_line(self.movehistory)
        self.game.headers["Event"] = "chess AI development"
        self.game.headers["Site"] = "Pune"
        self.game.headers["Date"] = str(datetime.datetime.now().date())
        self.game.headers["Round"] = 1
        self.game.headers["White"] = "Your AI bot" if self.game_state.player_one else "Standard Engine"
        self.game.headers["Black"] = "Your AI bot" if self.game_state.player_two else "Standard Engine"
        self.game.headers["Result"] = str(self.board.result(claim_draw=True))

    def checkStatus(self):
        if self.board.is_stalemate():
            speak("Its a draw by stalemate")
        elif self.board.is_checkmate():
            speak("Checkmate")
        elif self.board.is_insufficient_material():
            speak("Its a draw by insufficient material")
        elif self.board.is_check():
            speak("Check")


# Speak Function for the Assistant to speak
def speak(text):
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)  # Set index for voices currently 3 voices available
    engine.say(text)
    engine.runAndWait()


# Main Function
if __name__ == '__main__':
    # Lauch the window
    app = QApplication([])

    root_path = os.path.dirname(__file__)
    stockfish_rpath = r"engines\stockfish.exe"
    print(os.path.join(root_path, stockfish_rpath))

    window = MainWindow()
    window.engine = chess.engine.SimpleEngine.popen_uci(os.path.join(root_path, stockfish_rpath))    
    window.show()

    sys.exit(app.exec())