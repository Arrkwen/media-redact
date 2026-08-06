"""PP-OCR CTC 识别后处理。"""

from __future__ import annotations

from pathlib import Path

import numpy as np


class CTCLabelDecode:
    """CTC 解码，兼容 PP-OCRv4/v5 字典格式。"""

    def __init__(self, character_path: str | Path) -> None:
        self.character = self._load_character(character_path)
        self.dict = {char: index for index, char in enumerate(self.character)}

    @staticmethod
    def _load_character(character_path: str | Path) -> list[str]:
        character_list: list[str] = []
        with open(character_path, encoding="utf-8") as file:
            for line in file:
                character_list.append(line.strip("\n").strip("\r\n"))
        character_list.insert(0, "blank")
        character_list.append(" ")
        return character_list

    def decode(self, preds: np.ndarray) -> list[tuple[str, float]]:
        if preds.ndim == 2:
            preds = np.expand_dims(preds, axis=0)

        text_index = preds.argmax(axis=2)
        text_prob = preds.max(axis=2)
        results: list[tuple[str, float]] = []
        ignored_tokens = {0}

        for batch_idx in range(len(text_index)):
            tokens = text_index[batch_idx]
            selection = np.ones(len(tokens), dtype=bool)
            selection[1:] = tokens[1:] != tokens[:-1]
            for ignored in ignored_tokens:
                selection &= tokens != ignored

            if text_prob is not None:
                confidences = text_prob[batch_idx][selection]
                score = float(np.mean(confidences)) if len(confidences) else 0.0
            else:
                score = 1.0

            chars = [self.character[token_id] for token_id in tokens[selection]]
            results.append(("".join(chars), score))
        return results
