import os
import platform
import pygame


def get_korean_font(size: int) -> pygame.font.Font:
    system = platform.system()
    if system == "Darwin":
        path = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    elif system == "Windows":
        return pygame.font.SysFont("malgun gothic", size)
    else:
        for p in [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]:
            if os.path.exists(p):
                return pygame.font.Font(p, size)
    return pygame.font.SysFont(None, size)
