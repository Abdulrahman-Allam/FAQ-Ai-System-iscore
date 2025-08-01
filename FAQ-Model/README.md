---
tags:
- sentence-transformers
- cross-encoder
- generated_from_trainer
- dataset_size:28960
- loss:BinaryCrossEntropyLoss
base_model: MatMulMan/araelectra-base-discriminator-tydi-tafseer-pairs
pipeline_tag: text-ranking
library_name: sentence-transformers
---

# CrossEncoder based on MatMulMan/araelectra-base-discriminator-tydi-tafseer-pairs

This is a [Cross Encoder](https://www.sbert.net/docs/cross_encoder/usage/usage.html) model finetuned from [MatMulMan/araelectra-base-discriminator-tydi-tafseer-pairs](https://huggingface.co/MatMulMan/araelectra-base-discriminator-tydi-tafseer-pairs) using the [sentence-transformers](https://www.SBERT.net) library. It computes scores for pairs of texts, which can be used for text reranking and semantic search.

## Model Details

### Model Description
- **Model Type:** Cross Encoder
- **Base model:** [MatMulMan/araelectra-base-discriminator-tydi-tafseer-pairs](https://huggingface.co/MatMulMan/araelectra-base-discriminator-tydi-tafseer-pairs) <!-- at revision 7085ca8be3d1c45e2ce57f3d5dfb4c918ac1a37b -->
- **Maximum Sequence Length:** 512 tokens
- **Number of Output Labels:** 1 label
<!-- - **Training Dataset:** Unknown -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Documentation:** [Cross Encoder Documentation](https://www.sbert.net/docs/cross_encoder/usage/usage.html)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/UKPLab/sentence-transformers)
- **Hugging Face:** [Cross Encoders on Hugging Face](https://huggingface.co/models?library=sentence-transformers&other=cross-encoder)

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```

Then you can load this model and run inference.
```python
from sentence_transformers import CrossEncoder

# Download from the 🤗 Hub
model = CrossEncoder("cross_encoder_model_id")
# Get scores for pairs of texts
pairs = [
    ['بخصوص الاشتراكات، ممكن توضحلي مين بيدفع كام؟ يعني العامل بيساهم بقد إيه وصاحب الشغل بيكمل الباقي؟', 'أيوه، العامل له الحق يرفض التغييرات اللي بتضره، خصوصًا لو كانت في مواعيد الشغل، الراتب، أو طبيعة العمل. ولو صاحب العمل أصر، العامل يقدر يلجأ لمكتب العمل أو المحكمة المختصة.'],
    ['السؤال بالبلدي: الفلوس دي بندفعها للموظف لو قرر يسيب الشغل بعد سن معين، ولا دي بس للناس اللي الشركة بتستغنى عنهم؟', 'أيوه، العامل يقدر ياخد المكافأة حتى لو هو اللي قرر يسيب الشغل بعد سن الستين. مش لازم يكون اتفصل، المهم إن خدمته انتهت بعد ما كمل المدة المطلوبة.'],
    ['لو قررت امشي من الشركة، هل فيه ورق أو تصديق لازم اخده من مكتب العمل عشان اضمن حقي بعد كده؟ (تركيز على الحقوق بعد الاستقالة)', 'مدة فترة التجربة في أي عقد ماينفعش تزيد عن 3 شهور، وخلال المدة دي ينفع فسخ العقد من أي طرف بدون تعويض.'],
    ['لو أم بترضع طفلها في الشغل، وقت الرضاعة ده بيعتبر جزء من الدوام الرسمي بتاعها ولا لازم تعوضه بعدين؟', 'لو اتفقت مع الشركة كتابيًا إنك تلتزم بفترة معينة بعد التدريب، وسِبت الشغل قبل ما تكمّل المدة دي، ساعتها ممكن الشركة تطلب منك تدفع جزء من تكلفة التدريب، لكن لازم ده يكون مكتوب بوضوح في العقد.'],
    ['ممكن آخد المرتب بتاعي كله فلوس مباشرة من غير ما يتحط في البنك؟ ولا ده إجباري؟', 'نعم، الضرائب والتأمينات مش داخلة في الحد الأقصى للخصومات (الـ25%)، لأنها إلزامية من الدولة. يعني ممكن المرتب يتخصم منه ضرائب وتأمينات فوق الـ25% حسب القانون.'],
]
scores = model.predict(pairs)
print(scores.shape)
# (5,)

# Or rank different texts based on similarity to a single text
ranks = model.rank(
    'بخصوص الاشتراكات، ممكن توضحلي مين بيدفع كام؟ يعني العامل بيساهم بقد إيه وصاحب الشغل بيكمل الباقي؟',
    [
        'أيوه، العامل له الحق يرفض التغييرات اللي بتضره، خصوصًا لو كانت في مواعيد الشغل، الراتب، أو طبيعة العمل. ولو صاحب العمل أصر، العامل يقدر يلجأ لمكتب العمل أو المحكمة المختصة.',
        'أيوه، العامل يقدر ياخد المكافأة حتى لو هو اللي قرر يسيب الشغل بعد سن الستين. مش لازم يكون اتفصل، المهم إن خدمته انتهت بعد ما كمل المدة المطلوبة.',
        'مدة فترة التجربة في أي عقد ماينفعش تزيد عن 3 شهور، وخلال المدة دي ينفع فسخ العقد من أي طرف بدون تعويض.',
        'لو اتفقت مع الشركة كتابيًا إنك تلتزم بفترة معينة بعد التدريب، وسِبت الشغل قبل ما تكمّل المدة دي، ساعتها ممكن الشركة تطلب منك تدفع جزء من تكلفة التدريب، لكن لازم ده يكون مكتوب بوضوح في العقد.',
        'نعم، الضرائب والتأمينات مش داخلة في الحد الأقصى للخصومات (الـ25%)، لأنها إلزامية من الدولة. يعني ممكن المرتب يتخصم منه ضرائب وتأمينات فوق الـ25% حسب القانون.',
    ]
)
# [{'corpus_id': ..., 'score': ...}, {'corpus_id': ..., 'score': ...}, ...]
```

<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### Unnamed Dataset

* Size: 28,960 training samples
* Columns: <code>sentence_0</code>, <code>sentence_1</code>, and <code>label</code>
* Approximate statistics based on the first 1000 samples:
  |         | sentence_0                                                                                       | sentence_1                                                                                       | label                                                          |
  |:--------|:-------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------|:---------------------------------------------------------------|
  | type    | string                                                                                           | string                                                                                           | float                                                          |
  | details | <ul><li>min: 28 characters</li><li>mean: 110.24 characters</li><li>max: 320 characters</li></ul> | <ul><li>min: 16 characters</li><li>mean: 141.96 characters</li><li>max: 399 characters</li></ul> | <ul><li>min: 0.0</li><li>mean: 0.24</li><li>max: 1.0</li></ul> |
* Samples:
  | sentence_0                                                                                                                               | sentence_1                                                                                                                                                                                | label            |
  |:-----------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------|
  | <code>بخصوص الاشتراكات، ممكن توضحلي مين بيدفع كام؟ يعني العامل بيساهم بقد إيه وصاحب الشغل بيكمل الباقي؟</code>                           | <code>أيوه، العامل له الحق يرفض التغييرات اللي بتضره، خصوصًا لو كانت في مواعيد الشغل، الراتب، أو طبيعة العمل. ولو صاحب العمل أصر، العامل يقدر يلجأ لمكتب العمل أو المحكمة المختصة.</code> | <code>0.0</code> |
  | <code>السؤال بالبلدي: الفلوس دي بندفعها للموظف لو قرر يسيب الشغل بعد سن معين، ولا دي بس للناس اللي الشركة بتستغنى عنهم؟</code>           | <code>أيوه، العامل يقدر ياخد المكافأة حتى لو هو اللي قرر يسيب الشغل بعد سن الستين. مش لازم يكون اتفصل، المهم إن خدمته انتهت بعد ما كمل المدة المطلوبة.</code>                             | <code>1.0</code> |
  | <code>لو قررت امشي من الشركة، هل فيه ورق أو تصديق لازم اخده من مكتب العمل عشان اضمن حقي بعد كده؟ (تركيز على الحقوق بعد الاستقالة)</code> | <code>مدة فترة التجربة في أي عقد ماينفعش تزيد عن 3 شهور، وخلال المدة دي ينفع فسخ العقد من أي طرف بدون تعويض.</code>                                                                       | <code>0.0</code> |
* Loss: [<code>BinaryCrossEntropyLoss</code>](https://sbert.net/docs/package_reference/cross_encoder/losses.html#binarycrossentropyloss) with these parameters:
  ```json
  {
      "activation_fn": "torch.nn.modules.linear.Identity",
      "pos_weight": null
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `per_device_train_batch_size`: 16
- `per_device_eval_batch_size`: 16
- `num_train_epochs`: 5
- `disable_tqdm`: True

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `overwrite_output_dir`: False
- `do_predict`: False
- `eval_strategy`: no
- `prediction_loss_only`: True
- `per_device_train_batch_size`: 16
- `per_device_eval_batch_size`: 16
- `per_gpu_train_batch_size`: None
- `per_gpu_eval_batch_size`: None
- `gradient_accumulation_steps`: 1
- `eval_accumulation_steps`: None
- `torch_empty_cache_steps`: None
- `learning_rate`: 5e-05
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `max_grad_norm`: 1
- `num_train_epochs`: 5
- `max_steps`: -1
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: {}
- `warmup_ratio`: 0.0
- `warmup_steps`: 0
- `log_level`: passive
- `log_level_replica`: warning
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `save_safetensors`: True
- `save_on_each_node`: False
- `save_only_model`: False
- `restore_callback_states_from_checkpoint`: False
- `no_cuda`: False
- `use_cpu`: False
- `use_mps_device`: False
- `seed`: 42
- `data_seed`: None
- `jit_mode_eval`: False
- `use_ipex`: False
- `bf16`: False
- `fp16`: False
- `fp16_opt_level`: O1
- `half_precision_backend`: auto
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `local_rank`: 0
- `ddp_backend`: None
- `tpu_num_cores`: None
- `tpu_metrics_debug`: False
- `debug`: []
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_prefetch_factor`: None
- `past_index`: -1
- `disable_tqdm`: True
- `remove_unused_columns`: True
- `label_names`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `fsdp`: []
- `fsdp_min_num_params`: 0
- `fsdp_config`: {'min_num_params': 0, 'xla': False, 'xla_fsdp_v2': False, 'xla_fsdp_grad_ckpt': False}
- `fsdp_transformer_layer_cls_to_wrap`: None
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `deepspeed`: None
- `label_smoothing_factor`: 0.0
- `optim`: adamw_torch
- `optim_args`: None
- `adafactor`: False
- `group_by_length`: False
- `length_column_name`: length
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `skip_memory_metrics`: True
- `use_legacy_prediction_loop`: False
- `push_to_hub`: False
- `resume_from_checkpoint`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_private_repo`: None
- `hub_always_push`: False
- `hub_revision`: None
- `gradient_checkpointing`: False
- `gradient_checkpointing_kwargs`: None
- `include_inputs_for_metrics`: False
- `include_for_metrics`: []
- `eval_do_concat_batches`: True
- `fp16_backend`: auto
- `push_to_hub_model_id`: None
- `push_to_hub_organization`: None
- `mp_parameters`: 
- `auto_find_batch_size`: False
- `full_determinism`: False
- `torchdynamo`: None
- `ray_scope`: last
- `ddp_timeout`: 1800
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `include_tokens_per_second`: False
- `include_num_input_tokens_seen`: False
- `neftune_noise_alpha`: None
- `optim_target_modules`: None
- `batch_eval_metrics`: False
- `eval_on_start`: False
- `use_liger_kernel`: False
- `liger_kernel_config`: None
- `eval_use_gather_object`: False
- `average_tokens_across_devices`: False
- `prompts`: None
- `batch_sampler`: batch_sampler
- `multi_dataset_batch_sampler`: proportional

</details>

### Training Logs
| Epoch  | Step | Training Loss |
|:------:|:----:|:-------------:|
| 0.2762 | 500  | 0.5834        |
| 0.5525 | 1000 | 0.2288        |
| 0.8287 | 1500 | 0.1489        |
| 1.1050 | 2000 | 0.1207        |
| 1.3812 | 2500 | 0.1102        |
| 1.6575 | 3000 | 0.0987        |
| 1.9337 | 3500 | 0.0813        |
| 2.2099 | 4000 | 0.0759        |
| 2.4862 | 4500 | 0.0675        |
| 2.7624 | 5000 | 0.0621        |
| 3.0387 | 5500 | 0.0535        |
| 3.3149 | 6000 | 0.0568        |
| 3.5912 | 6500 | 0.0494        |
| 3.8674 | 7000 | 0.0449        |
| 4.1436 | 7500 | 0.0471        |
| 4.4199 | 8000 | 0.0446        |
| 4.6961 | 8500 | 0.0508        |
| 4.9724 | 9000 | 0.0386        |


### Framework Versions
- Python: 3.11.13
- Sentence Transformers: 4.1.0
- Transformers: 4.54.0
- PyTorch: 2.6.0+cu124
- Accelerate: 1.9.0
- Datasets: 4.0.0
- Tokenizers: 0.21.2

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->