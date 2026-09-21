from typing import Any

import numpy as np
import numpy.typing as npt

class BudgetExceeded(Exception): ...
def reduce_f2(
    offsets: npt.NDArray[np.int64], values: npt.NDArray[np.int64], evidence: str,
    max_columns: int, max_stored_entries: int, max_xor_steps: int,
    max_trace_entries: int, max_output_bytes: int,
) -> dict[str, Any]: ...
