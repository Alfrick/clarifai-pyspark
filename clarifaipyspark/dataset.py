from clarifai.client.app import App
from clarifai.client.dataset import Dataset
from clarifai.client.input import Inputs
from clarifai.client.user import User
from google.protobuf.json_format import MessageToJson
from pyspark.sql import SparkSession


class Dataset(Dataset):
  """Dataset class provides information about dataset of the app and it inherits from the clarifai SDK Dataset class."""

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
                              input_type: str = 'text',
                              csv_type: str = None,
                              labels: bool = True,
                              chunk_size: int = 128) -> None:
    """Uploads dataset into clarifai app from the csv file path.

    Args:
        csv_path (str): CSV file path of the dataset to be uploaded into clarifai App.
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
    ### TODO: Can input column names & extract them to convert to our csv format
    super().upload_from_csv(
        csv_path=csv_path,
        input_type=input_type,
        csv_type=csv_type,
        labels=labels,
        chunk_size=chunk_size)

  def upload_from_folder(self,
                         folder_path: str = "",
                         input_type: str = 'text',
                         labels: bool = False,
                         chunk_size: int = 128) -> None:
    """Uploads dataset from folder into clarifai app.

    Args:
        folder_path (str): folder path of the dataset to be uploaded into clarifai App.
        input_type (str): Input type of the dataset whether (Image, text).
        labels (bool): Give True if labels column present in dataset else False.
        chunk_size (int): chunk size of parallel uploads of inputs and annotations.

    Example: TODO

    Note:
        Can provide a volume or S3 path to the folder
        If label is true, then folder name is class name (label)
    """

    super().upload_from_folder(
        folder_path=folder_path, input_type=input_type, labels=labels, chunk_size=chunk_size)

  def upload_dataset_from_dataloader(self,
                                     task: str,
                                     split: str,
                                     module_dir: str = None,
                                     dataset_loader: str = None,
                                     chunk_size: int = 128) -> None:
    """Uploads dataset using a dataloader function for custom formats.

    Args:
        task (str): task type(text_clf, visual-classification, visual_detection, visual_segmentation, visual-captioning).
        split (str): split type(train, test, val).
        module_dir (str): path to the module directory.
        dataset_loader (str): name of the dataset loader.
        chunk_size (int): chunk size for concurrent upload of inputs and annotations.

    Example: TODO
    """
    super().upload_dataset(task, split, module_dir, dataset_loader, chunk_size)

  def upload_dataset_from_table(self,
                                table_path: str,
                                task: str,
                                split: str,
                                input_type: str,
                                table_type: str,
                                labels: bool,
                                module_dir: str = None,
                                dataset_loader=None,
                                chunk_size: int = 128) -> None:
    """upload dataset into clarifai app from spark tables.

    Args:
        table_path (str): path of the table to be uploaded.
        task (str):
        split (str):
        input_type (str): Input type of the dataset whether (Image, text).
        table_type (str): Type of the table contents (url, raw, filepath).
        labels (bool): Give True if labels column present in dataset else False.
        module_dir (str): path to the module directory.
        dataset_loader (str): name of the dataset loader.
        chunk_size (int): chunk size for concurrent upload of inputs and annotations.
    Note:
        Accepted csv format - input, label
        TODO: dataframe dataloader template
        TODO: Can input column names & extreact them to convert to our csv format
    """

    if dataset_loader:
      super().upload_dataset(task, split, module_dir, dataset_loader, chunk_size)

    else:
      # df = sqlContext.table(table_path)
      csv_path = "./"
      # df.write.option("header", True).option("delimiter",",").csv(csv_path)
      spark = SparkSession.builder.appName('Clarifai-spark').getOrCreate()
      df_delta = spark.read.format("delta").load(table_path)
      df_delta.createTempView("temporary_view")
      # convert the temporary view into a CSV file
      csv_path = table_path.replace(".delta", ".csv")
      spark.sql("SELECT * FROM temporary_view").write.option("header",
                                                             "true").format("csv").save(csv_path)
      super().upload_from_csv(
          csv_path=csv_path,
          input_type=input_type,
          csv_type=table_type,
          labels=labels,
          chunk_size=chunk_size)

  def list_inputs_from_dataset(self,
                               dataset_id: str = None,
                               per_page: int = None,
                               input_type: str = None):
    """Lists all the inputs from the app.

    Args:
        dataset_id (str): dataset_id of which the inputs needs to be listed.
        per_page (str): No of response of inputs per page.
        input_type (str): Input type that needs to be displayed (text,image)
        TODO: Do we need input_type ?, since in our case it is image, so probably we can go with default value of "image".

    Examples:
        TODO

    Returns:
        list of inputs.
        """
    input_obj = Inputs(user_id=self.user_id, app_id=self.app_id)
    return list(
        input_obj.list_inputs(dataset_id=dataset_id, input_type=input_type, per_page=per_page))

  def list_annotations(self, dataset_id: str = None, per_page: int = None, input_type: str = None):
    """Lists all the annotations for the inputs in the dataset of a clarifai app.

    Args:
        dataset_id (str): dataset_id of which the inputs needs to be listed.
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
    all_inputs = list(
        input_obj.list_inputs(dataset_id=dataset_id, input_type=input_type, per_page=per_page))
    return list(input_obj.list_annotations(batch_input=all_inputs))

  def export_annotations_to_dataframe(self):
    """Export all the annotations from clarifai App into spark dataframe.

    Examples:
        TODO

    Returns:
        spark dataframe with annotations"""

    annotation_list = []
    spark = SparkSession.builder.appName('Clarifai-spark').getOrCreate()
    input_obj = Inputs(user_id=self.user_id, app_id=self.app_id)
    all_inputs = list(input_obj.list_inputs(dataset_id=dataset_id))
    response = input_obj.list_annotations(batch_input=all_inputs)
    annotation_list.append(MessageToJson(response.annotations))
    #Need to get the details of rest of the columns (ID, URL), annotations should be appended along with the existing dataframe created while dataset upload
    data = [annotation_list]
    df = spark.createDataFrame(data)
    return df
