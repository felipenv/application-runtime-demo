import pickle
import yaml

if __name__=="__main__":
    config = yaml.safe_load(open("config/config.yaml"))
    data = pickle.load(open("data/dataset.pkl", 'rb'))