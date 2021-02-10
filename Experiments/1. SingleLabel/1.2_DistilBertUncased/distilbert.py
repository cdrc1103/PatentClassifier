""" Dependencies """
# Load Huggingface transformer
from transformers import TFDistilBertModel, DistilBertConfig, DistilBertTokenizerFast

# Then what you need from tensorflow.keras
from tensorflow.keras.layers import Input, Dropout, Dense
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint, TensorBoard
from tensorflow.keras.initializers import TruncatedNormal
from tensorflow.keras.losses import CategoricalCrossentropy
from tensorflow.keras.metrics import CategoricalAccuracy, Precision, Recall
from tensorflow.keras.utils import to_categorical
import tensorflow as tf

# Some addons
from tensorflow_addons.metrics import F1Score

# Libraries to import and process the data set
import pandas as pd
import numpy as np

# Visualization
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns

# Utilities
from contextlib import redirect_stdout
import pathlib
import json

""" Directories and filenames """
# Define some names
experiment_name = "1.2_DistilBertUncased" # name of the experiment
version = "v1"
base_dir = pathlib.Path(f"gdrive/MyDrive/Colab Notebooks/Thesis/{experiment_name}")
train_dataset = pathlib.Path.joinpath(base_dir, "train.csv")  # where to read the data from
val_dataset = pathlib.Path.joinpath(base_dir, "val.csv")
test_dataset = pathlib.Path.joinpath(base_dir, "test.csv")
model_name = 'distilbert-base-uncased'
logdir = pathlib.Path.joinpath(base_dir, f"logs_{version}")
# Read data
train = pd.read_csv(train_dataset)
val = pd.read_csv(val_dataset)
test = pd.read_csv(test_dataset)
n_classes = len(train["label_encoded"].unique()) # number of unique classes. since the train-test-split is stratified
                                                # we can be sure all classes are present in train

""" Class weights """
# Determine class weights to tackle class imbalance
class_weight = {}
total_instances = len(train)
class_freqs = train["label_encoded"].value_counts()
for class_id, freq in zip(class_freqs.index, class_freqs):
    class_weight[class_id] = (1 / freq)*(total_instances)/2.0
sample_weight = []
for class_id in train["label_encoded"]:
    sample_weight.append(class_weight[class_id])

""" Parameters """
# Dataset
max_token_length = 200 # number of tokens per example

# Training
batch_size = 16
epochs = 3 # iterate over full dataset x times
random_state = 1000
prefetch_size = 2

# Adam Optimizer
learning_rate = 5e-05
epsilon = 1e-08
decay = 0.01
clipnorm = 1.0

hyperparameters = {
    "max_token_length": max_token_length,
    "batch_size": batch_size,
    "epochs": epochs,
    "optimizer": {
        "name": "Adam",
        "learning_rate": learning_rate,
        "epsilon": epsilon,
        "decay": decay,
        "clipnorm": clipnorm
    }
}
with open(pathlib.Path.joinpath(base_dir, f"hyperparameters_{version}.json"), 'w') as file:
    json.dump(hyperparameters, file)

""" Callbacks """
checkpoint_callback = ModelCheckpoint(filepath=pathlib.Path.joinpath(base_dir, f"checkpoint_{version}.ckpt"),
                              save_weights_only=True, verbose=1,
                              monitor='val_loss',  mode='auto', save_freq='epoch')
tensorboard_callback = TensorBoard(logdir, histogram_freq=1, write_graph=False, write_images=True,
                                   update_freq=100, embeddings_freq=1, )

""" Transformer and tokenizer config """
# Load transformers config
config = DistilBertConfig.from_pretrained(model_name)
config.output_hidden_states = False
with open(pathlib.Path.joinpath(base_dir, f'config_{version}.txt'), 'w') as file: # save config to dir
    with redirect_stdout(file):
        print(config)

tokenizer = DistilBertTokenizerFast.from_pretrained(pretrained_model_name_or_path=model_name, config=config)
train_encodings = tokenizer(train["abstract"].to_list(), truncation=True, padding=True, max_length=max_token_length)
val_encodings = tokenizer(val["abstract"].to_list(), truncation=True, padding=True, max_length=max_token_length)
test_encodings = tokenizer(test["abstract"].to_list(), truncation=True, padding=True, max_length=max_token_length)

def to_tfdataset(x_encoded, y):
    y = to_categorical(y, num_classes=n_classes)
    return tf.data.Dataset.from_tensor_slices((dict(x_encoded), y))
train_ds = to_tfdataset(train_encodings, train["label"])
val_ds = to_tfdataset(val_encodings, val["label"])

y_test = to_categorical(test['label'], num_classes=n_classes)

""" Model architecture """
# Load the Transformers BERT model
transformer_model = TFDistilBertModel.from_pretrained(model_name, config=config) # loads all pretrained weights
# Load the MainLayer
bert = transformer_model.layers[0]

# Build model input
input_ids = Input(shape=max_token_length, name='input_ids', dtype='int64')
inputs = {'input_ids': input_ids}

# Build model output
# Load the Transformers BERT model as a layer in a Keras model
bert_model = bert(inputs)[1]
# Add dropout layer for regularization
dropout_layer = Dropout(config.dropout, name='regularization_layer') # dropout_prob=0.1
dropout = dropout_layer(bert_model, training=False)
# Add dense layer to condense to the number of classes
dense = Dense(units=n_classes,
              kernel_initializer=TruncatedNormal(stddev=config.initializer_range),
              name='dense', activation='softmax')(dropout)
outputs = {'label': dense}
# Combine it all in a model object
model = Model(inputs=inputs, outputs=outputs, name=experiment_name)

# Print model summary and save it
with open(pathlib.Path.joinpath(base_dir, f'summary_{version}.txt'), 'w') as file:
    # Pass the file handle in as a lambda function to make it callable
    model.summary(print_fn=lambda x: file.write(x + '\n'))

# Set an optimizer
optimizer = Adam(
    learning_rate=learning_rate,
    epsilon=epsilon,
    decay=decay,
    clipnorm=clipnorm)

# Set loss and metrics
loss = {'label': CategoricalCrossentropy(from_logits=False)}

metric = [CategoricalAccuracy(name='accuracy'),
          Precision(name='precision'), # Precision is the percentage of predicted positives that were correctly classified
          Recall(name='recall'), # Recall is the percentage of actual positives that were correctly classified
          F1Score(name='f1score', num_classes=n_classes, average='macro')]

""" Training """
# Compile the model
model.compile(
    optimizer=optimizer,
    loss=loss,
    metrics=metric)

# Fit the model
history = model.fit(
    x={'input_ids': train_ds.shuffle(random_state).batch(batch_size).prefetch(prefetch_size)},
    validation_data={'input_ids': val_ds.shuffle(random_state).batch(batch_size).prefetch(prefetch_size)},
    epochs=epochs,
    callbacks=[tensorboard_callback, checkpoint_callback],
    verbose=1,
    sample_weight=np.array(sample_weight))

hist_df = pd.DataFrame(history.history)
hist_df.to_csv(pathlib.Path.joinpath(base_dir, f"history_{version}.csv"))

"""" Evaluation """
# plot the metric history from training
def plot_metrics(history):
    metrics = ['accuracy', 'f1score', 'precision', 'recall']
    fig = plt.figure()
    for n, metric in enumerate(metrics):
        name = metric.replace("_", " ").capitalize()
        plt.subplot(2, 2, n+1)
        plt.plot(history.epoch, history.history[metric], label="Train")
        plt.plot(history.epoch, history.history['val_'+metric], label="Validation")
        plt.grid()
        plt.xlabel("Epoch")
        plt.ylabel(name)
        plt.ylim([0,1])
        plt.legend(loc='upper left')
        plt.xticks(np.arange(0, epochs), np.arange(1, epochs))
    plt.tight_layout()
    fig.savefig(pathlib.Path.joinpath(base_dir, f"metrics_{version}"), dpi=150)

plot_metrics(history)

def plot_cm(labels, predictions):
    cm = confusion_matrix(labels, predictions, labels=np.arange(0,n_classes))
    sum_per_label = np.sum(cm, axis=1)
    cm_norm = cm / sum_per_label[:, None]
    cm_norm =np.round(cm_norm, 2)
    fig = plt.figure(figsize=(15,7))
    sns.heatmap(cm_norm, annot=True, fmt=".2f")
    plt.xlabel('Predicted label')
    plt.ylabel('Actual label')
    plt.tight_layout()
    fig.savefig(pathlib.Path.joinpath(base_dir, f"confusion_{version}"), dpi=150)

predictions = model.predict(
    x={'input_ids': test_encodings},
    batch_size=batch_size
)
# Create confusion matrix from results
predictions =np.argmax(predictions["label"], axis=1) # select the prediction with highest probability
y_test = np.argmax(y_test, axis=1) # select the true label from one-hot encoding
plot_cm(y_test, predictions)

# Calculate classification report
cls_names =[str(cls) for cls in np.arange(0, n_classes)]
cls_report = classification_report(y_test, predictions, target_names=cls_names, output_dict=True)
cls_report = pd.DataFrame(cls_report).round(2)
cls_report.to_csv(pathlib.Path.joinpath(base_dir, f"metrics_report_{version}.csv"))