import re

class TextChunker:
    def chunk(self, text: str, max_chars: int = 500, overlap: int = 50) -> list[str]:
        if not text:
            return []

        # Split on sentence boundaries: . ? ! followed by space or end of string.
        # Preserve punctuation.
        raw_sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        chunks = []
        current_sentences = []
        current_len = 0

        for sentence in sentences:
            # If a single sentence exceeds max_chars, split it character-wise
            if len(sentence) > max_chars:
                # Flush current queue
                if current_sentences:
                    chunks.append(" ".join(current_sentences))
                    current_sentences = []
                    current_len = 0
                
                # Split character-wise with overlap
                start = 0
                while start < len(sentence):
                    end = start + max_chars
                    chunk_part = sentence[start:end]
                    chunks.append(chunk_part)
                    
                    step = max(1, max_chars - overlap)
                    start += step
                    if start >= len(sentence):
                        break
                continue

            # Check if this sentence fits in the current chunk
            space_needed = 1 if current_sentences else 0
            if current_len + space_needed + len(sentence) > max_chars:
                # Flush the current chunk
                chunks.append(" ".join(current_sentences))

                # Extract overlap sentences from the end of the flushed chunk
                overlap_sentences = []
                overlap_len = 0
                for s in reversed(current_sentences):
                    s_space = 1 if overlap_sentences else 0
                    if (overlap_len + s_space + len(s) <= overlap) and \
                       (overlap_len + s_space + len(s) + 1 + len(sentence) <= max_chars):
                        overlap_sentences.insert(0, s)
                        overlap_len += s_space + len(s)
                    else:
                        break
                current_sentences = overlap_sentences
                current_len = overlap_len

            # Add the sentence to current chunk
            space_needed = 1 if current_sentences else 0
            current_sentences.append(sentence)
            current_len += space_needed + len(sentence)

        # Flush any remaining sentences
        if current_sentences:
            chunks.append(" ".join(current_sentences))

        return chunks
