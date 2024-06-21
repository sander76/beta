from pathlib import Path

import cairosvg
import pytest
from clipstick import parse
from clipstick._help import console
from pydantic import BaseModel

import tests
from tests import HELP_OUTPUT_FOLDER
from tests.models import dataclass_models, pydantic_models

TEST_FOLDER = Path(tests.__file__).parent


@pytest.fixture(params=[dataclass_models, pydantic_models])
def models(request):
    return request.param


class CapturedOutput:
    def __init__(self, fixture_request) -> None:
        self.captured_output: str | None = None
        self._fixture_request = fixture_request

    def __call__(self, model: type[BaseModel], args: list[str]) -> None:
        try:
            console.width = 1000
            console.record = True
            parse(model, args)

        finally:
            self.captured_output = console.export_text(clear=False)
            lines = self.captured_output.split("\n")
            max_length = max((len(line) for line in lines))
            console.width = max_length
            svg = console.export_svg(title="help output")

            file_path = Path(self._fixture_request.fspath)
            relative_from_test = file_path.relative_to(TEST_FOLDER)
            output = HELP_OUTPUT_FOLDER / relative_from_test.with_suffix("")

            output.mkdir(exist_ok=True, parents=True)

            target_base_file = output / self._fixture_request.function.__name__
            raw_text_file = target_base_file.with_suffix(".txt")
            raw_text_file.write_text(self.captured_output, encoding="utf-8")

            cairosvg.svg2png(
                svg,
                write_to=str(
                    (output / self._fixture_request.function.__name__).with_suffix(
                        ".png"
                    )
                ),
            )


@pytest.fixture(scope="function")
def capture_output(request) -> CapturedOutput:
    # set this very long width. othewise rich will assume the console with of your ide window
    # and potentially wrap output breaking your tests.
    # console.width = 1000
    captured_output = CapturedOutput(request)

    yield captured_output
    console.clear()
    console.record = False
