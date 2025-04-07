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

def decision_weighted(probs):
    """Règle du vote pondéré : Choisir la classe avec la somme maximale des probabilités."""
    sum_probs = np.sum(probs, axis=0)
    return classnames[np.argmax(sum_probs)]


import numpy as np
import pickle
from tensorflow.keras.models import load_model

root = os.path.dirname(os.path.abspath(__file__))

def old_model_prediction(payload):
    this_fv = np.frombuffer(payload, dtype=np.uint16)
    
    ocsvm_filename = root + "/ocsvm_model.pkl"
    cnn_filename = root + "/CNN_model.keras"
    
    ocsvm_model = pickle.load(open(ocsvm_filename, "rb"))
    cnn_model = load_model(cnn_filename)
    
    my_little_norm = np.linalg.norm(this_fv)
    this_fv = this_fv / my_little_norm
    
    ocsvm_prediction = ocsvm_model.predict([this_fv])
    # if ocsvm_prediction[0] == -1:
    #     return None, None
    
    demo_fv = this_fv.reshape((1, 20, 20, 1))
    prediction = cnn_model.predict(demo_fv.T)

    return prediction, this_fv



old_predictions = []
model = tf.keras.models.load_model(root + "/CNN_model.keras")
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
    return decision_maxlikelihood(old_predictions), this_fv, prediction[0]
        