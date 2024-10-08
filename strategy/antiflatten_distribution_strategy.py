import torch
from .backtrack_strategy import BacktrackStrategy
from typing import List, Optional, Tuple

class AntiFlattenDistributionStrategy(BacktrackStrategy):
    def __init__(self, cumulative_prob_threshold: float=0.35, ratio_threshold: float=1.5):
        self.cumulative_prob_threshold = cumulative_prob_threshold
        self.ratio_threshold = ratio_threshold
        self._is_flat = False
        self._backtrack_position = None
        self._keep_index = 0

    def get_keep_index(self) -> int:
        return self._keep_index

    def on_logits(self, logits: torch.FloatTensor, continuation_tokens: List[int]) -> torch.FloatTensor:
        #only apply it if we just backtracked
        if self._is_flat and self._backtrack_position != None:
            logits[:, self._backtrack_position[1]] = torch.finfo(logits.dtype).max
            self._backtrack_position = None
        return logits

    def on_probs(self, probs: torch.FloatTensor, continuation_tokens: List[int]) -> torch.FloatTensor:
        self._is_flat = self._is_distribution_flat(probs)
        return probs

    def on_next_token(self, continuation_tokens: List[int], probs: torch.FloatTensor) -> None:
        latest_token = continuation_tokens[-1]
        highest_prob_token = torch.argmax(probs).item()

        if latest_token != highest_prob_token:
            self._keep_index = len(continuation_tokens) - 1
            self._backtrack_position = (self._keep_index, highest_prob_token)
        else:
            if self._backtrack_position is None:
                self._keep_index += 1

    def backtrack(self, 
                  continuation_tokens: List[int],
                  past_key_values: Optional[Tuple[Tuple[torch.Tensor, ...], ...]]) -> Tuple[List[int], int, Optional[Tuple[Tuple[torch.Tensor, ...], ...]]]:
        if self._is_flat and self._backtrack_position != None:
            current_position = len(continuation_tokens)
            initial_position = current_position

            while current_position > self._backtrack_position[0]:
                continuation_tokens.pop()
                current_position -= 1

            if past_key_values:
                past_key_values = tuple(tuple(layer[:, :, :current_position - initial_position, :] for layer in kv_pair) for kv_pair in past_key_values)
            
        return continuation_tokens, past_key_values

    def _is_distribution_flat(self, probs):
        """
        Determines if the distribution over the top tokens is flat.
    
        Args:
            probs (torch.Tensor or array-like): A 1D tensor or list of token probabilities.
            cumulative_prob_threshold (float): The cumulative probability threshold to select top tokens.
            ratio_threshold (float): The maximum allowed ratio between the top two probabilities for flatness.
    
        Returns:
            bool: True if the distribution is flat, False otherwise.
        """
        # Flatten probs to a 1D tensor
        probs = probs.view(-1)
    
        # Sort the probabilities in descending order
        sorted_probs, _ = torch.sort(probs, descending=True)
    
        # Compute the cumulative probabilities
        cumulative_probs = torch.cumsum(sorted_probs, dim=0)
    
        # Find the number of top tokens needed to reach the cumulative probability threshold
        num_top_tokens = torch.searchsorted(cumulative_probs, self.cumulative_prob_threshold).item() + 1

        # Get the probabilities of the top tokens
        top_probs = sorted_probs[:num_top_tokens]

        # Ensure there are at least two tokens to compare
        if num_top_tokens < 2:
            return False  # Not enough tokens to judge flatness
    
        # Get the top two probabilities
        max_prob = top_probs[0].item()

        # +1e-8 to avoid division by 0
        last_max_prob = top_probs[-1].item() + 1e-8
    
        # Compute the ratio
        ratio = max_prob / last_max_prob
        
        # Determine if the distribution is flat
        return ratio <= self.ratio_threshold