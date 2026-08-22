import math
import sys
import threading
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QGuiApplication, QPolygon, QFont, QLinearGradient
from PyQt6.QtWidgets import QApplication, QWidget


class OverlayScreen(QWidget):
    def __init__(self, stockfish_queue):
        super().__init__()
        self.stockfish_queue = stockfish_queue

        # Set the window to be the size of the screen
        self.screen = QGuiApplication.screens()[0]
        self.setFixedWidth(self.screen.size().width())
        self.setFixedHeight(self.screen.size().height())

        # Set the window to be transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        # A list of QPolygon objects containing the points of the arrows
        self.arrows = []
        
        # Evaluation bar properties
        self.eval_bar_visible = False
        self.eval_value = 0.0
        self.eval_type = "cp"  # "cp" for centipawns or "mate" for mate
        self.eval_text = "0.00"
        self.is_white = True  # Default assumption
        
        # Board position, will be updated
        self.board_position = None
        
        # Evaluation bar dimensions
        self.eval_bar_width = 45
        self.eval_bar_height = 400
        self.eval_bar_x = 20  # Default x position
        self.eval_bar_y = (self.height() - self.eval_bar_height) // 2  # Default y position
        self.eval_bar_margin = 18  # Margin between board and eval bar

        # Color scheme for flashy look
        self.COLOR_ACCENT = QColor(233, 69, 96)  # #e94560
        self.COLOR_GOLD = QColor(255, 215, 0)    # #ffd700
        self.COLOR_GREEN = QColor(0, 255, 136)    # #00ff88
        self.COLOR_DARK_BG = QColor(26, 26, 46)   # #1a1a2e
        self.COLOR_ARROW_RED = QColor(255, 50, 50, 160)

        # Start the message queue thread
        self.message_queue_thread = threading.Thread(target=self.message_queue_thread)
        self.message_queue_thread.start()

    def message_queue_thread(self):
        """
        This thread is used to receive messages from the stockfish message queue
        and update the arrows
        Args:
            None
        Returns:
            None
        """

        while True:
            message = self.stockfish_queue.get()
            if isinstance(message, list):
                # Arrow data
                self.set_arrows(message)
            elif isinstance(message, dict) and "eval" in message:
                # Evaluation data
                eval_value = message["eval"]
                eval_type = message.get("eval_type", "cp")
                
                # Update board position if provided
                if "board_position" in message:
                    self.board_position = message["board_position"]
                    self.update_eval_bar_position()
                
                # Update bot color if provided
                if "is_white" in message:
                    self.is_white = message["is_white"]
                
                self.update_eval_bar(eval_value, eval_type)
    
    def update_eval_bar_position(self):
        """
        Update the evaluation bar position based on the chess board position
        """
        if not self.board_position:
            return
            
        # Position the eval bar to the left of the board with a small margin
        self.eval_bar_x = self.board_position['x'] - self.eval_bar_width - self.eval_bar_margin
        
        # Make the eval bar the exact same height as the board
        self.eval_bar_height = self.board_position['height']
        self.eval_bar_y = self.board_position['y']
            
    def update_eval_bar(self, eval_value, eval_type="cp"):
        """
        Update the evaluation bar with a new value
        Args:
            eval_value: The evaluation value (float for centipawns, int for mate)
            eval_type: "cp" for centipawns or "mate" for mate
        """
        self.eval_bar_visible = True
        self.eval_type = eval_type
        self.eval_value = eval_value
        
        # Format text display
        if eval_type == "cp":
            self.eval_text = f"{eval_value:.2f}"
        else:  # mate
            self.eval_text = f"M{eval_value}"
        
        self.update()

    def set_arrows(self, arrows):
        """
        This function is used to set the arrows to be drawn on the screen
        Args:
            arrows: A list of tuples containing the start and end position of the arrows
            in the form of ((start_point, end_point), (start_point, end_point))
        Returns:
            None
        """

        self.arrows = []
        for arrow in arrows:
            poly = self.get_arrow_polygon(
                QPoint(arrow[0][0], arrow[0][1]),
                QPoint(arrow[1][0], arrow[1][1])
            )
            self.arrows.append(poly)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw arrows with glow effect
        painter.setPen(QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(self.COLOR_ARROW_RED, Qt.BrushStyle.SolidPattern))
        for arrow in self.arrows:
            # Glow effect - draw slightly larger semi-transparent version
            painter.setBrush(QBrush(QColor(255, 0, 0, 60)))
            painter.drawPolygon(self.expand_polygon(arrow, 4))
            # Main arrow
            painter.setBrush(QBrush(self.COLOR_ARROW_RED))
            painter.drawPolygon(arrow)
        
        # Draw evaluation bar if visible
        if self.eval_bar_visible:
            self.draw_eval_bar(painter)
        
        painter.end()
    
    def expand_polygon(self, polygon, pixels):
        """Create an expanded version of the polygon for glow effect."""
        points = []
        center_x = sum(p.x() for p in polygon) / polygon.size()
        center_y = sum(p.y() for p in polygon) / polygon.size()
        for i in range(polygon.size()):
            p = polygon.at(i)
            dx = p.x() - center_x
            dy = p.y() - center_y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 0:
                nx = dx / dist
                ny = dy / dist
            else:
                nx, ny = 0, 0
            points.append(QPoint(
                int(p.x() + nx * pixels),
                int(p.y() + ny * pixels)
            ))
        return QPolygon(points)
    
    def draw_eval_bar(self, painter):
        """
        Draw the evaluation bar on the screen with modern flashy style
        Args:
            painter: QPainter object
        """
        # Bar background / border with glow
        border_rect = QRect(
            self.eval_bar_x - 3, 
            self.eval_bar_y - 3, 
            self.eval_bar_width + 6, 
            self.eval_bar_height + 6
        )
        # Glow effect border
        painter.setPen(QPen(self.COLOR_GOLD, 2))
        painter.setBrush(QBrush(QColor(10, 10, 20, 200)))
        painter.drawRoundedRect(border_rect, 6, 6)
        
        # Inner bar area
        inner_rect = QRect(
            self.eval_bar_x, 
            self.eval_bar_y, 
            self.eval_bar_width, 
            self.eval_bar_height
        )
        
        # The eval value is already from the player's perspective
        # (positive = advantage for the player, negative = advantage for opponent)
        if self.eval_type == "cp":
            value = max(min(float(self.eval_value), 10.0), -10.0)
            player_advantage = 1.0 / (1.0 + math.exp(-value * 0.5))  # Sigmoid function
        else:  # mate
            mate_value = int(self.eval_value)
            if mate_value > 0:  # Mate for player
                player_advantage = 1.0  # Maximum advantage - full bar
            else:  # Mate for opponent
                player_advantage = 0.0  # Minimum advantage - no bar
        
        # Set colors based on player's color with gradients
        if self.is_white:
            bottom_color = QColor(245, 245, 235, 240)  # Warm white
            top_color = QColor(30, 30, 40, 230)       # Dark
            bot_grad = QLinearGradient(0, 0, 0, 30)
            bot_grad.setColorAt(0.0, QColor(255, 255, 255, 220))
            bot_grad.setColorAt(1.0, QColor(200, 200, 200, 240))
            top_grad = QLinearGradient(0, 0, 0, 30)
            top_grad.setColorAt(0.0, QColor(40, 40, 50, 230))
            top_grad.setColorAt(1.0, QColor(20, 20, 30, 230))
        else:
            bottom_color = QColor(30, 30, 40, 230)    # Dark
            top_color = QColor(245, 245, 235, 240)    # Warm white
            bot_grad = QLinearGradient(0, 0, 0, 30)
            bot_grad.setColorAt(0.0, QColor(40, 40, 50, 230))
            bot_grad.setColorAt(1.0, QColor(20, 20, 30, 230))
            top_grad = QLinearGradient(0, 0, 0, 30)
            top_grad.setColorAt(0.0, QColor(255, 255, 255, 220))
            top_grad.setColorAt(1.0, QColor(200, 200, 200, 240))
        
        # Calculate section heights
        player_height = int(self.eval_bar_height * player_advantage)
        opponent_height = self.eval_bar_height - player_height
        
        # Draw opponent's section (top) with gradient
        opponent_rect = QRect(
            self.eval_bar_x + 2, 
            self.eval_bar_y + 2, 
            self.eval_bar_width - 4, 
            opponent_height - 2 if opponent_height > 2 else 0
        )
        painter.setPen(Qt.PenStyle.NoPen)
        if opponent_height > 2:
            painter.setBrush(QBrush(self._darken(top_color, 0.8)))
            painter.drawRect(opponent_rect)
        
        # Draw player's section (bottom) with gradient
        player_rect = QRect(
            self.eval_bar_x + 2, 
            self.eval_bar_y + opponent_height, 
            self.eval_bar_width - 4, 
            player_height - 2 if player_height > 2 else 0
        )
        if player_height > 2:
            painter.setBrush(QBrush(self._darken(bottom_color, 1.2)))
            painter.drawRect(player_rect)
        
        # Draw the center line with accent color
        center_y = self.eval_bar_y + (self.eval_bar_height // 2)
        painter.setPen(QPen(self.COLOR_GOLD, 2))
        painter.drawLine(
            self.eval_bar_x + 2, 
            center_y, 
            self.eval_bar_x + self.eval_bar_width - 2, 
            center_y
        )
        
        # Draw a small accent dot at center
        painter.setBrush(QBrush(self.COLOR_ACCENT))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(self.eval_bar_x + self.eval_bar_width // 2, center_y), 3, 3)
        
        # Draw evaluation text with modern style
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        
        # Format the display text
        display_text = self.eval_text
        if self.eval_type == "cp" and float(self.eval_value) > 0:
            display_text = "+" + display_text
            
        # Position text at the bottom
        text_rect = QRect(
            self.eval_bar_x + 2, 
            self.eval_bar_y + self.eval_bar_height - 22, 
            self.eval_bar_width - 4, 
            20
        )
        
        # Draw text background with glassmorphism effect
        painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(text_rect, 3, 3)
        
        # Draw text with gold color
        painter.setPen(QPen(self.COLOR_GOLD))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, display_text)
        
        # Draw "W" and "B" labels at top and bottom
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        
        # Top label (opponent's color)
        top_label_rect = QRect(
            self.eval_bar_x + 2,
            self.eval_bar_y + 4,
            self.eval_bar_width - 4,
            14
        )
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.drawRoundedRect(top_label_rect, 2, 2)
        label_color = QColor(200, 200, 200) if self.is_white else QColor(60, 60, 60)
        painter.setPen(QPen(label_color))
        painter.drawText(top_label_rect, Qt.AlignmentFlag.AlignCenter, "W" if self.is_white else "B")
        
        # Bottom label (player's color)
        bot_label_rect = QRect(
            self.eval_bar_x + 2,
            self.eval_bar_y + self.eval_bar_height - 38,
            self.eval_bar_width - 4,
            14
        )
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.drawRoundedRect(bot_label_rect, 2, 2)
        label_color = QColor(60, 60, 60) if self.is_white else QColor(200, 200, 200)
        painter.setPen(QPen(label_color))
        painter.drawText(bot_label_rect, Qt.AlignmentFlag.AlignCenter, "B" if self.is_white else "W")

    def _darken(self, color, factor):
        """Darken or lighten a color."""
        r = min(255, max(0, int(color.red() * factor)))
        g = min(255, max(0, int(color.green() * factor)))
        b = min(255, max(0, int(color.blue() * factor)))
        return QColor(r, g, b, color.alpha())

    def get_arrow_polygon(self, start_point, end_point):
        """
        This function is used to get the polygon for the arrow
        Args:
            start_point: The start point of the arrow
            end_point: The end point of the arrow
        Returns:
            A QPolygon object containing the points of the arrow
        """

        try:
            dx, dy = start_point.x() - end_point.x(), start_point.y() - end_point.y()

            # Normalize the vector
            leng = math.sqrt(dx ** 2 + dy ** 2)
            norm_x, norm_y = dx / leng, dy / leng

            # Get the perpendicular vector
            perp_x = -norm_y
            perp_y = norm_x

            arrow_height = 25
            left_x = end_point.x() + arrow_height * norm_x * 1.5 + arrow_height * perp_x
            left_y = end_point.y() + arrow_height * norm_y * 1.5 + arrow_height * perp_y

            right_x = end_point.x() + arrow_height * norm_x * 1.5 - arrow_height * perp_x
            right_y = end_point.y() + arrow_height * norm_y * 1.5 - arrow_height * perp_y

            point2 = QPoint(int(left_x), int(left_y))
            point3 = QPoint(int(right_x), int(right_y))

            mid_point1 = QPoint(int((2 / 5) * point2.x() + (3 / 5) * point3.x()), int((2 / 5) * point2.y() + (3 / 5) * point3.y()))
            mid_point2 = QPoint(int((3 / 5) * point2.x() + (2 / 5) * point3.x()), int((3 / 5) * point2.y() + (2 / 5) * point3.y()))

            start_left = QPoint(int(start_point.x() + (arrow_height / 5) * perp_x), int(start_point.y() + (arrow_height / 5) * perp_y))
            start_right = QPoint(int(start_point.x() - (arrow_height / 5) * perp_x), int(start_point.y() - (arrow_height / 5) * perp_y))

            return QPolygon([end_point, point2, mid_point1, start_right, start_left, mid_point2, point3])
        except Exception as e:
            print(e)


def run(stockfish_queue):
    """
    This function is used to run the overlay
    Args:
        stockfish_queue: The message queue used to communicate with the stockfish thread
    Returns:
        None
    """

    app = QApplication(sys.argv)
    overlay = OverlayScreen(stockfish_queue)
    overlay.show()
    app.exec()
