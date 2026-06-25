import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from attendance_page import render

# Book Date: date range driven by the transaction date (T_TRANSDATE)
render("T_TRANSDATE", "Book Date")
