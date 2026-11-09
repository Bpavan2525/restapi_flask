# Vercel entry point: every request is routed here (see vercel.json).
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shop_api import create_app

app = create_app()
