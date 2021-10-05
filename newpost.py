import os

import string
import random

title = str()

for i in range(8):
    title += random.choice(string.hexdigits)

os.system(f"hugo new posts/{title}.md")
