from typing import Any

import numpy as np
import numpy.typing as npt

class BudgetExceeded(Exception): ...
def reduce_f2(
    offsets: npt.NDArray[np.int64], values: npt.NDArray[np.int64], evidence: str,
    max_columns: int, max_stored_entries: int, max_xor_steps: int,
    max_trace_entries: int, max_output_bytes: int,
) -> dict[str, Any]: ...

def assess_polygonal(
    vertices: npt.NDArray[np.float64], edges: npt.NDArray[np.int64],
    offsets: npt.NDArray[np.int64], coedges: npt.NDArray[np.int64], unit: str,
    max_input_bytes: int = ..., max_owned_bytes: int = ...,
    max_work_steps: int = ..., max_output_bytes: int = ...,
) -> dict[str, Any]: ...
