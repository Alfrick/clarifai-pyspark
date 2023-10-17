from clarifai.client.app import App
from clarifai.client.base import BaseClient
from clarifai.client.user import User


class ClarifaiPySpark(BaseClient):
  """ClarifaiPySpark inherits the BaseClient class from the clarifai SDK and it initializes the client."""

  def __init__(self, user_id: str = "", app_id: str = ""):
    """Initializes clarifai client object.

    Args:
      - user_id (str): A user ID for authentication.
      - app_id (str): An app ID for the application to interact with.
  """

    self.user = User(user_id=user_id)
    self.app = App(app_id=app_id)
    #Inputs object - for listannotations
    #input_obj = User(user_id="user_id").app(app_id="app_id").inputs()
    self.user_id = user_id
    self.app_id = app_id
    super().__init__(user_id=user_id, app_id=app_id)

  def dataset(self, dataset_id):
    """Initializes the dataset method with dataset_id.

    Args:
        dataset_id: The dataset_id within the user app.

    Returns:
           Dataset object for the dataset_id.
      """

    self.dataset_id = dataset_id
    try:
      self.dataset = self.app.dataset(dataset_id=dataset_id)
    except:
      print("Creating a new dataset")
      self.dataset = self.app.create_dataset(dataset_id=dataset_id)
    return self.dataset
