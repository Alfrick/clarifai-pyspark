import json
import time
import uuid
from typing import Generator, List

import requests
from clarifai.client.app import App
from clarifai.client.dataset import Dataset
from clarifai.client.input import Inputs
from clarifai.client.user import User
from clarifai.errors import UserError
from clarifai_grpc.grpc.api.resources_pb2 import Annotation, Input
from google.protobuf.struct_pb2 import Struct
from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import SparkSession


class Dataset(Dataset):
  """
  Dataset class provides information about dataset of the app
  and it inherits from the clarifai SDK Dataset class.
  """

  def __init__(self, user_id: str = "", app_id: str = "", dataset_id: str = ""):
    """Initializes the Dataset object.

    Args:
        user_id (str): The clarifai user ID of the user.
        app_id (str): Clarifai App ID.
        dataset_id (str): Dataset ID of the dataset inside the clarifai App.

    Example: TODO
    """
    self.user = User(user_id=user_id)
    self.app = App(app_id=app_id)
    #Inputs object - for listannotations
    #input_obj = User(user_id="user_id").app(app_id="app_id").inputs()
    self.user_id = user_id
    self.app_id = app_id
    self.dataset_id = dataset_id
    super().__init__(user_id=user_id, app_id=app_id, dataset_id=dataset_id)

  def upload_dataset_from_csv(self,
                              csv_path: str = "",
                              source: str = "volume",
                              input_type: str = 'text',
                              csv_type: str = None,
                              labels: bool = True,
                              chunk_size: int = 128) -> None:
    """Uploads dataset to clarifai app from the csv file path.

    Args:
        csv_path (str): CSV file path of the dataset to be uploaded into clarifai App.
        source (str): Source for csv file whether (volume, s3)
        input_type (str): Input type of the dataset whether (Image, text).
        csv_type (str): Type of the csv file contents(url, raw, filepath).
        labels (bool): Give True if labels column present in dataset else False.
        chunk_size (int): chunk size of parallel uploads of inputs and annotations.

    Example: TODO

    Note:
        CSV file supports 'inputid', 'input', 'concepts', 'metadata', 'geopoints' columns.
        All the data in the CSV should be in double quotes.
        metadata should be in single quotes format. Example: "{'key': 'value'}"
        geopoints should be in "long,lat" format.

    """
    if source == "volume":
      self.upload_from_csv(
          csv_path=csv_path,
          input_type=input_type,
          csv_type=csv_type,
          labels=labels,
          chunk_size=chunk_size)
    elif source == "s3":
      spark = SparkSession.builder.appName('Clarifai-spark').getOrCreate()
      df_csv = spark.read.format("csv").option('header', 'true').load(csv_path)
      self.upload_dataset_from_dataframe(
          dataframe=df_csv,
          input_type=input_type,
          df_type=csv_type,
          labels=labels,
          chunk_size=chunk_size)
    else:
      raise UserError("Source should be one of 'volume' or 's3'")

  def upload_dataset_from_folder(self,
                                 folder_path: str,
                                 input_type: str,
                                 labels: bool = False,
                                 chunk_size: int = 128) -> None:
    """Uploads dataset from folder into clarifai app.

    Args:
        folder_path (str): folder path of the dataset to be uploaded into clarifai App.
        input_type (str): Input type of the dataset whether (Image, text).
        labels (bool): Give True if folder name is a label name else False.
        chunk_size (int): chunk size of parallel uploads of inputs and annotations.

    Example: TODO

    Note:
        Can provide a volume or S3 path to the folder
        If label is true, then folder name is class name (label)
    """

    self.upload_from_folder(
        folder_path=folder_path, input_type=input_type, labels=labels, chunk_size=chunk_size)

  def _get_inputs_from_dataframe(self,
                                 dataframe,
                                 input_type: str,
                                 df_type: str,
                                 dataset_id: str = None,
                                 labels: str = True) -> List[Input]:
    input_protos = []
    input_obj = Inputs(user_id=self.user_id, app_id=self.app_id)

    for row in dataframe.collect():
      if labels:
        labels_list = row["concepts"].split(',')
        labels = labels_list if len(row['concepts']) > 0 else None
      else:
        labels = None

      if 'metadata' in dataframe.columns:
        if row['metadata'] is not None and len(row['metadata']) > 0:
          metadata_str = row['metadata'].replace("'", '"')
          try:
            metadata_dict = json.loads(metadata_str)
          except json.decoder.JSONDecodeError:
            raise UserError("metadata column in CSV file should be a valid json")
          metadata = Struct()
          metadata.update(metadata_dict)
        else:
          metadata = None
      else:
        metadata = None

      if 'geopoints' in dataframe.columns:
        if row['geopoints'] is not None and len(row['geopoints']) > 0:
          geo_points = row['geopoints'].split(',')
          geo_points = [float(geo_point) for geo_point in geo_points]
          geo_info = geo_points if len(geo_points) == 2 else UserError(
              "geopoints column in CSV file should have longitude,latitude")
        else:
          geo_info = None
      else:
        geo_info = None

      input_id = row['inputid'] if 'inputid' in dataframe.columns else uuid.uuid4().hex
      text = row["input"] if input_type == 'text' else None
      image = row['input'] if input_type == 'image' else None
      video = row['input'] if input_type == 'video' else None
      audio = row['input'] if input_type == 'audio' else None

      if df_type == 'raw':
        input_protos.append(
            input_obj.get_text_input(
                input_id=input_id,
                raw_text=text,
                dataset_id=dataset_id,
                labels=labels,
                metadata=metadata,
                geo_info=geo_info))
      elif df_type == 'url':
        input_protos.append(
            input_obj.get_input_from_url(
                input_id=input_id,
                image_url=image,
                text_url=text,
                audio_url=audio,
                video_url=video,
                dataset_id=dataset_id,
                labels=labels,
                metadata=metadata,
                geo_info=geo_info))
      else:
        input_protos.append(
            input_obj.get_input_from_file(
                input_id=input_id,
                image_file=image,
                text_file=text,
                audio_file=audio,
                video_file=video,
                dataset_id=dataset_id,
                labels=labels,
                metadata=metadata,
                geo_info=geo_info))

    return input_protos

  def upload_dataset_from_dataframe(self,
                                    dataframe,
                                    input_type: str,
                                    df_type: str = None,
                                    labels: bool = True,
                                    chunk_size: int = 128) -> None:
    """Uploads dataset from a dataframe.
       Expected columns in the dataframe are inputid, input, concepts (optional), metadata (optional), geopoints (optional).

      Args:
          dataframe (SparkDataFrame): Spark dataframe with image/text URLs and labels.
          input_type (str): Input type of the dataset whether (Image, text).
          labels (bool): Give True if folder name is a label name else False.
          chunk_size (int): chunk size of parallel uploads of inputs and annotations.

      Example: TODO
    """

    if input_type not in ('image', 'text'):
      raise UserError('Invalid input type, it should be image or text')

    if df_type not in ('raw', 'url', 'file_path'):
      raise UserError('Invalid csv type, it should be raw, url or file_path')

    if df_type == 'raw' and input_type != 'text':
      raise UserError('Only text input type is supported for raw csv type')

    if not isinstance(dataframe, SparkDataFrame):
      raise UserError('dataframe should be a Spark DataFrame')

    chunk_size = min(128, chunk_size)
    input_obj = input_obj = Inputs(user_id=self.user_id, app_id=self.app_id)
    input_protos = self._get_inputs_from_dataframe(
        dataframe=dataframe,
        df_type=df_type,
        input_type=input_type,
        dataset_id=self.dataset_id,
        labels=labels)
    return (input_obj._bulk_upload(inputs=input_protos, chunk_size=chunk_size))

  def upload_dataset_from_dataloader(self,
                                     task: str,
                                     split: str,
                                     module_dir: str = None,
                                     chunk_size: int = 128) -> None:
    """Uploads dataset using a dataloader function for custom formats.

    Args:
        task (str): task type(text_clf, visual-classification, visual_detection, visual_segmentation, visual-captioning).
        split (str): split type(train, test, val).
        module_dir (str): path to the module directory.
        chunk_size (int): chunk size for concurrent upload of inputs and annotations.

    Example: TODO
    """
    self.upload_dataset(task=task, split=split, module_dir=module_dir, chunk_size=chunk_size)

  def upload_dataset_from_table(self,
                                table_path: str,
                                input_type: str,
                                table_type: str,
                                labels: bool,
                                chunk_size: int = 128) -> None:
    """upload dataset to clarifai app from spark tables.

    Args:
        table_path (str): path of the table to be uploaded.
        input_type (str): Input type of the dataset whether (Image, text).
        table_type (str): Type of the table contents (url, raw, filepath).
        labels (bool): Give True if labels column present in dataset else False.
        chunk_size (int): chunk size for concurrent upload of inputs and annotations.

    Example: TODO
    """
    spark = SparkSession.builder.appName('Clarifai-spark').getOrCreate()
    tempdf = spark.read.format("delta").load(table_path)
    self.upload_dataset_from_dataframe(
        dataframe=tempdf,
        input_type=input_type,
        df_type=table_type,
        labels=labels,
        chunk_size=chunk_size)

  def list_inputs(self, per_page: int = None,
                  input_type: str = None) -> Generator[Input, None, None]:
    """Lists all the inputs from the app.

    Args:
        per_page (str): No of response of inputs per page.
        input_type (str): Input type that needs to be displayed (text,image)

    Examples:
        TODO

    Returns:
        list of inputs.
    """
    if input_type not in ('image', 'text'):
      raise UserError('Invalid input type, it should be image or text')
    input_obj = Inputs(user_id=self.user_id, app_id=self.app_id)
    return input_obj.list_inputs(
        dataset_id=self.dataset_id, input_type=input_type, per_page=per_page)

  def list_annotations(self, input_ids: list = None, per_page: int = None,
                       input_type: str = None) -> Generator[Annotation, None, None]:
    """Lists all the annotations for the inputs in the dataset of a clarifai app.

    Args:
        input_ids (list): list of input_ids for which user wants annotations
        per_page (str): No of response of inputs per page.
        input_type (str): Input type that needs to be displayed (text,image)
        TODO: Do we need input_type ?, since in our case it is image, so probably we can go with default value of "image".

    Examples:
        TODO

    Returns:
        list of annotations.
    """
    ### input_ids: list of input_ids for which user wants annotations
    input_obj = Inputs(user_id=self.user_id, app_id=self.app_id)
    if not input_ids:
      all_inputs = list(
          input_obj.list_inputs(
              dataset_id=self.dataset_id, input_type=input_type, per_page=per_page))
    else:
      all_inputs = [
          input_obj._get_proto(input_id=inpid, dataset_id=self.dataset_id) for inpid in input_ids
      ]
    return input_obj.list_annotations(batch_input=all_inputs)

  def export_annotations_to_dataframe(self, input_ids: list = None, input_type: str = None):
    """Export all the annotations from clarifai App's dataset to spark dataframe.

    Args:
        input_ids (list): list of input_ids for which user wants annotations
        input_type (str): Input type that needs to be displayed (text,image)
    Examples:
        TODO

    Returns:
        spark dataframe with annotations
    """

    annotation_list = []
    spark = SparkSession.builder.appName('Clarifai-spark').getOrCreate()
    response = list(self.list_annotations(input_ids=input_ids, input_type=input_type))
    for an in response:
      temp = {}
      temp['annotation'] = str(an.data)
      if not temp['annotation'] or temp['annotation'] == '{}':
        continue
      temp['annotation_id'] = an.id
      temp['annotation_user_id'] = an.user_id
      temp['input_id'] = an.input_id
      try:
        created_at = float(f"{an.created_at.seconds}.{an.created_at.nanos}")
        temp['annotation_created_at'] = time.strftime('%m/%d/% %H:%M:%5', time.gmtime(created_at))
        modified_at = float(f"{an.modified_at.seconds}.{an.modified_at.nanos}")
        temp['annotation_modified_at'] = time.strftime('%m/%d/% %H:%M:%5',
                                                       time.gmtime(modified_at))
      except:
        temp['annotation_created_at'] = float(f"{an.created_at.seconds}.{an.created_at.nanos}")
        temp['annotation_modified_at'] = float(f"{an.modified_at.seconds}.{an.modified_at.nanos}")
      annotation_list.append(temp)
    return spark.createDataFrame(annotation_list)

  def export_images_to_volume(self, path, input_response):
    """Download all the images from clarifai App's dataset to spark volume storage.

    Args:
        path (str): path of the volume storage where images will be downloaded.
        input_response (list): response of list_inputs() method.

    Examples:
        TODO

    Returns:
        None. Images are saved into the volume storage.
    """
    for resp in input_response:
      imgid = resp.id
      ext = resp.data.image.image_info.format
      url = resp.data.image.url
      img_name = path + '/' + imgid + '.' + ext.lower()
      headers = {"Authorization": self.metadata[0][1]}
      response = requests.get(url, headers=headers)
      with open(img_name, "wb") as f:
        f.write(response.content)

  def export_text_to_volume(self, path, input_response):
    """Download all the text files from clarifai App's dataset to spark volume storage.

    Args:
        path (str): path of the volume storage where images will be downloaded.
        input_response (list): response of list_inputs() method.

    Examples:
        TODO

    Returns:
        None. text files are saved into the volume storage.
    """
    for resp in input_response:
      textid = resp.id
      url = resp.data.text.url
      file_name = path + '/' + textid + '.txt'
      enc = resp.data.text.text_info.encoding
      headers = {"Authorization": self.metadata[0][1]}
      response = requests.get(url, headers=headers)
      with open(file_name, "a", encoding=enc) as f:
        f.write(response.content.decode())

  def export_inputs_to_dataframe(self, input_type):
    """Export all the inputs from clarifai App's dataset to spark dataframe.

    Args:
        input_type (str): Input type that needs to be fetched (text,image)

    Examples:
        TODO

    Returns:
        spark dataframe with inputs
    """
    if input_type not in ('image', 'text'):
      raise UserError('Invalid input type, it should be image or text')
    input_list = []
    spark = SparkSession.builder.appName('Clarifai-spark').getOrCreate()
    response = list(self.list_inputs(input_type=input_type))
    for inp in response:
      temp = {}
      temp['input_id'] = inp.id
      if input_type == 'image':
        temp['image_url'] = inp.data.image.url
        temp['image_info'] = str(inp.data.image.image_info)
      elif input_type == 'text':
        temp['text_url'] = inp.data.text.url
        temp['text_info'] = str(inp.data.text.text_info)
      try:
        created_at = float(f"{inp.created_at.seconds}.{inp.created_at.nanos}")
        temp['input_created_at'] = time.strftime('%m/%d/% %H:%M:%5', time.gmtime(created_at))
        modified_at = float(f"{inp.modified_at.seconds}.{inp.modified_at.nanos}")
        temp['input_modified_at'] = time.strftime('%m/%d/% %H:%M:%5', time.gmtime(modified_at))
      except:
        temp['input_created_at'] = float(f"{inp.created_at.seconds}.{inp.created_at.nanos}")
        temp['input_modified_at'] = float(f"{inp.modified_at.seconds}.{inp.modified_at.nanos}")
      input_list.append(temp)
    return spark.createDataFrame(input_list)

  def export_dataset_to_dataframe(self, input_type, input_ids: list = None):
    """Export all the inputs & their annotations from clarifai App's dataset to spark dataframe.

    Args:
        input_type (str): Input type that needs to be fetched (text,image)
        input_ids (list): list of input_ids for which user wants annotations

    Examples:
        TODO

    Returns:
        spark dataframe with inputs & their annotations
    """
    inputs_df = self.export_inputs_to_dataframe(input_type=input_type)
    annotations_df = self.export_annotations_to_dataframe(input_ids=input_ids)
    return inputs_df.join(
        annotations_df, inputs_df.input_id == annotations_df.input_id,
        how='left').drop(annotations_df.input_id)
