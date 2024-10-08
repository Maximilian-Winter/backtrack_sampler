import torch
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

class BacktrackStrategy(ABC):
    @abstractmethod
    def get_keep_index(self) -> int:
        """
        We keep in memory without sending to the client (yet) the tokens starting from this index
        because we might want to rollback at a future point in time.
        Everything up until (but not included!) this index
        is considered valid token generation that can't be rollbacked and therefore
        can be sent to the client for its use.
        """
        pass

    @abstractmethod
    def backtrack(self, continuation_tokens: list[int]) -> Tuple[int, Optional[Tuple[Tuple[torch.Tensor, ...], ...]]]:
        pass

    @abstractmethod
    def on_logits(self, logits: torch.FloatTensor, continuation_tokens: List[int]) -> torch.FloatTensor:
        pass

    @abstractmethod
    def on_probs(self, probs: torch.FloatTensor, continuation_tokens: List[int]) -> torch.FloatTensor:
        pass

    @abstractmethod
    def on_next_token(self, continuation_tokens: List[int], probs: torch.FloatTensor) -> None:
        pass