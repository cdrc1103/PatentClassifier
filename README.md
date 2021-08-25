# Multi-Label Classification for Cosmetic Patents Using Neural Networks
The aim of this thesis is to identify, implement, and evaluate suitable approaches for the classification of patents in the cosmetic domain using neural networks. For this purpose, a patent collection provided by the company Beiersdorf is used as application case. Particular to this patent collection is a company-internal labeling hierarchy that assigns a variable number of labels to each patent in correspondence to the product fields of Beiersdorf. In the course of this thesis, state-of-the-art neural network architectures like convolutional and recurrent neural networks as well as Transformers are applied to the patent data and evaluated regarding their ability to assign the correct labels to unknown patent instances. Properties of the considered data collection, that affect the performance of neural networks, are identified and implications for the prediction accuracy are inferred. A set of solutions is developed that leverages the special characteristics and different features found in a patent document to research the feasibility of automatically recommending labels for unknown patent instances with a high accuracy.

## Structure of the Repository

```
Data
|   Database: Initialization of the database in with a docker yml file
|   Feature and label parsing
|   Description of the data

Experiments
└───Multi Class Classification: One label per instance
       │   GRU Models: Classification based on the Gated Recurrent Unit
       │   CNN Models: Classification based on Convolutional Neural Networks
       │   BERT Models: Classification based on BERT contextual embeddings
└───Multi Label Classification: One or more labels per instance
       |   BERT Models: Classification based on BERT contextual embeddings
       |   BERT Ensemble: Classification based on several concatenated bert layers

Utilities: Some tools to work with the data
```
