import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from attendance_page import render

# Event Date: date range driven by the event/calendar date (TI_CALDATE)
render("TI_CALDATE", "Event Date")
