"""
@author: Heerozh (Zhang Jianhao)
@copyright: Copyright 2019, Heerozh. All rights reserved.
@license: Apache 2.0
@email: heeroz@gmail.com
"""
from typing import Optional, Sequence, Union
from ..parallel import nanlast
from .factor import BaseFactor, CustomFactor
import torch


class DataFactor(BaseFactor):
    def __init__(self, inputs: Optional[Sequence[str]] = None,
                 is_data_after_market_close=True) -> None:
        super().__init__()
        if inputs:
            self.inputs = inputs
        assert (3 > len(self.inputs) > 0), \
            "DataFactor's `inputs` can only contains one data column and corresponding " \
            "adjustments column"
        self._data = None
        self._multi = None
        self.is_data_after_market_close = is_data_after_market_close

    @property
    def adjustments(self):
        return self._multi

    def get_total_backwards_(self) -> int:
        return 0

    def is_close_data_used(self) -> bool:
        return self.is_data_after_market_close

    def pre_compute_(self, engine, start, end) -> None:
        super().pre_compute_(engine, start, end)
        self._data = engine.column_to_tensor_(self.inputs[0])
        self._data = engine.group_by_(self._data, self.groupby)
        if len(self.inputs) > 1 and self.inputs[1] in engine.dataframe_:
            self._multi = engine.column_to_tensor_(self.inputs[1])
            self._multi = engine.group_by_(self._multi, self.groupby)
        else:
            self._multi = None

    def clean_up_(self) -> None:
        super().clean_up_()
        self._data = None
        self._multi = None

    def compute_(self, stream: Union[torch.cuda.Stream, None]) -> torch.Tensor:
        return self._data

    def compute(self, *inputs: Sequence[torch.Tensor]) -> torch.Tensor:
        pass


class AdjustedDataFactor(CustomFactor):
    def __init__(self, data: DataFactor):
        super().__init__(1, (data,))
        self.parent = data

    def compute(self, data) -> torch.Tensor:
        multi = self.parent.adjustments
        if multi is None:
            return data
        return data * multi / nanlast(multi, dim=1)[:, None]


class AssetClassifierDataFactor(BaseFactor):
    """dict to categorical output for asset"""
    def __init__(self, sector: dict, default: int):
        super().__init__()
        self.sector = sector
        self.default = default
        self._data = None

    def get_total_backwards_(self) -> int:
        return 0

    def is_close_data_used(self) -> bool:
        return False

    def pre_compute_(self, engine, start, end) -> None:
        super().pre_compute_(engine, start, end)
        assets = engine.dataframe_index[1]
        sector = self.sector
        default = self.default
        data = [sector.get(asset, default) for asset in assets]
        data = torch.tensor(data, device=engine.device, dtype=torch.float32)
        self._data = engine.group_by_(data, self.groupby)

    def clean_up_(self) -> None:
        super().clean_up_()
        self._data = None

    def compute_(self, stream: Union[torch.cuda.Stream, None]) -> torch.Tensor:
        return self._data

    def compute(self, *inputs: Sequence[torch.Tensor]) -> torch.Tensor:
        pass
