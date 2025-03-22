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


import numpy as np
import pickle
from tensorflow.keras.models import load_model

def old_model_prediction(payload):
    classnames = ['chainsaw', 'fire', 'fireworks', 'gun']
    this_fv = np.frombuffer(payload, dtype=np.uint16)
    
    ocsvm_filename = "auth/src/auth/ocsvm_model.pkl"
    cnn_filename = "auth/src/auth/CNN_model.keras"
    
    # Charger les modèles
    ocsvm_model = pickle.load(open(ocsvm_filename, "rb"))
    cnn_model = load_model(cnn_filename)
    
    # Normalisation du vecteur de caractéristiques
    my_little_norm = np.linalg.norm(this_fv)
    this_fv = this_fv / my_little_norm
    
    # Prédiction avec OCSVM
    ocsvm_prediction = ocsvm_model.predict([this_fv])
    if ocsvm_prediction[0] == 1:
        return None
    
    new_shape = (20, 20, 1)
    demo_fv = this_fv.reshape(new_shape)
    
    # Prédiction avec le CNN
    prediction = cnn_model.predict(demo_fv)
    
    # Obtenir la classe avec la probabilité la plus élevée
    predicted_class = classnames[np.argmax(prediction)]
    
    return predicted_class


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
    return decision_maxlikelihood(old_predictions), this_fv, prediction[0]
        