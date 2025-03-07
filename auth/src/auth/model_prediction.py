import os
import matplotlib.pyplot as plt
import numpy as np
import pickle
import sklearn
import tensorflow as tf

classnames = ['chainsaw', 'fire', 'fireworks', 'gun']
def decision_maxlikelihood(probs):
    """Règle du maximum de vraisemblance : Choisir la classe avec le produit maximal des probabilités."""
    probs = np.array(probs)
    prod_probs = np.prod(probs, axis=0)
    return classnames[np.argmax(prod_probs)]


def old_model_prediction(payload):
    this_fv = np.frombuffer(payload, dtype=np.uint16)
    # fm_dir = "data/feature_matrices/"  # where to save the features matrices
    filename = "auth/src/auth/model.pickle"
    model = pickle.load(open(filename, "rb"))
    mat = np.zeros((2, len(this_fv)))
    my_little_norm = np.linalg.norm(this_fv)
    if my_little_norm < 40:
        return None
    this_fv = this_fv / np.linalg.norm(this_fv)
    mat[0] = this_fv
    prediction = model.predict(mat)
    return prediction[0]

old_predictions = []
model = tf.keras.models.load_model("auth/src/auth/CNN_model.keras")
def model_prediction(payload):
    this_fv = np.frombuffer(payload, dtype=np.uint16)
    mat = np.zeros((2, len(this_fv)))
    this_fv = this_fv / np.linalg.norm(this_fv)
    mat[0] = this_fv
    prediction = model.predict(mat)
    if len(old_predictions) < 4:
        old_predictions.append(prediction[0])
    if len(old_predictions) == 4:
        old_predictions.pop(0)
        old_predictions.append(prediction[0])
    return decision_maxlikelihood(old_predictions)
        