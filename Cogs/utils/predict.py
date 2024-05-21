import cv2
import typing
import numpy as np
from .path import MBTG_MODEL
from mltu.configs import BaseModelConfigs
from mltu.inferenceModel import OnnxInferenceModel
from mltu.utils.text_utils import ctc_decoder

MODEL_CONF = f"{MBTG_MODEL}/configs.yaml"
MODEL_VAL = f"{MBTG_MODEL}/val.csv"

class ImageToWordModel(OnnxInferenceModel):
    def __init__(self, char_list: typing.Union[str, list], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.char_list = char_list

    def predict(self, image: np.ndarray):
        image = cv2.resize(image, self.input_shapes[0][1:3][::-1])
        image_pred = np.expand_dims(image, axis=0).astype(np.float32)
        preds = self.model.run(self.output_names, {self.input_names[0]: image_pred})[0]
        text = ctc_decoder(preds, self.char_list)[0]
        return text

def predict(image_path: str):
    configs = BaseModelConfigs.load(MODEL_CONF)
    model = ImageToWordModel(model_path=configs.model_path, char_list=configs.vocab)
    image = cv2.imread(image_path)
    return model.predict(image)