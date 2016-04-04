from itertools import product
from sklearn.metrics import auc, roc_curve, matthews_corrcoef
import common
import glob
import numpy as np
import os
import pandas as pd
import prepare_data
import pylab
import time

def get_ranks(input_array):
    """Get the ranks of the elements in an array.
    
    :param input_array: input array
    :type input_array: numpy array
    :return: the ranks of the elements
    :rtype: numpy array
    """

    order = input_array.argsort()
    ranks = order.argsort()
    return ranks

def compute_MCC(y_true, y_score, threshold_num=500):
    """Compute the Matthews Correlation Coefficient.
    
    :param y_true: true binary labels in range {0, 1}
    :type y_true: numpy array
    :param y_score: the probability estimates of the positive class
    :type y_score: numpy array
    :param threshold_num: the number of thresholds
    :type threshold_num: int
    :return: the maximum Matthews Correlation Coefficient
    :rtype: float
    """

    # Get the ranks
    ranks = get_ranks(y_score)

    # Generate the array which contains the value of thresholds
    threshold_array = np.linspace(np.min(ranks) - 1, np.max(ranks) + 1, num=threshold_num)

    # Generate MCC values
    MCC_list = []
    for threshold in threshold_array:
        MCC_list.append(matthews_corrcoef(y_true, ranks > threshold))
    MCC_array = np.array(MCC_list)

    # Illustrate threshold and MCC values
    # pylab.figure()
    # pylab.plot(threshold_array / np.max(ranks), MCC_array)
    # pylab.show()

    return np.max(MCC_array)

def perform_interpolation(x_array, y_array, threshold_array):
    """Perform interpolation on the ROC curve.
    
    :param x_array: the data along the x axis
    :type x_array: numpy array
    :param y_array: the data along the y axis
    :type y_array: numpy array
    :param threshold_array: the thresholds along the y axis where interpolation is needed
    :type threshold_array: numpy array
    :return: the interpolated x_array and y_array
    :rtype: tuple
    """

    for threshold in threshold_array:
        # Neglect the interpolation if the threshold is aleady in y_array
        if np.sum(y_array == threshold) > 0:
            continue

        # Find the index which meets y_array[previous_index] < threshold
        # and y_array[previous_index+1] > threshold
        previous_index = np.max(np.argwhere(y_array < threshold))
        following_index = previous_index + 1

        # Insert the interpolated data to y_array and x_array.
        # The interpolated data is generated by using linear interpolation.
        value = (threshold - y_array[previous_index]) * (x_array[following_index] - x_array[previous_index]) / \
            (y_array[following_index] - y_array[previous_index]) + x_array[previous_index]
        y_array = np.insert(y_array, following_index, threshold)
        x_array = np.insert(x_array, following_index, value)

    return (x_array, y_array)

def compute_Weighted_AUC(y_true, y_score, weight_distribution=np.arange(4, -1, -1.0)):
    """Compute the Weighted AUC score.
    
    :param y_true: true binary labels in range {0, 1}
    :type y_true: numpy array
    :param y_score: the probability estimates of the positive class
    :type y_score: numpy array
    :param weight_distribution: the weights of different areas
    :type weight_distribution: numpy array
    :return: the Weighted AUC score
    :rtype: float
    """

    # Divide the range [0, 1] evenly
    weight_num = weight_distribution.shape[0]
    evenly_spaced_thresholds = np.linspace(0, 1, num=weight_num + 1)

    # Compute ROC curve and perform interpolation
    fpr, tpr, _ = roc_curve(y_true, y_score)
    fpr, tpr = perform_interpolation(fpr, tpr, evenly_spaced_thresholds[1:-1])

    # Plot ROC curve
    # pylab.figure()
    # pylab.plot(fpr, tpr)
    # pylab.axis("equal")
    # pylab.grid()
    # pylab.xlabel("False Positive Rate")
    # pylab.ylabel("True Positive Rate")
    # pylab.title("ROC Curve")
    # pylab.show()

    # Compute the areas
    area_array = np.zeros(weight_num)
    lowest_record_index = 0
    for area_index in range(weight_num):
        # Compute the highest index of the records within current area
        high_threshold = evenly_spaced_thresholds[area_index + 1]
        highest_record_index = np.sum(tpr <= high_threshold) - 1

        # Select the records within current area
        selected_fpr = fpr[lowest_record_index:highest_record_index + 1]
        selected_tpr = tpr[lowest_record_index:highest_record_index + 1]

        # Remove bias in True Positive Rate
        selected_tpr = selected_tpr - selected_tpr[0]

        # Extend the curve to the range [0, 1]
        selected_fpr = np.hstack(([0], selected_fpr, [1]))
        selected_tpr = np.hstack((selected_tpr[0], selected_tpr, selected_tpr[-1]))

        # Plot selected ROC curve
        # pylab.figure()
        # pylab.plot(selected_fpr, selected_tpr)
        # pylab.axis("equal")
        # pylab.grid()
        # pylab.xlabel("False Positive Rate")
        # pylab.ylabel("True Positive Rate")
        # pylab.title("Selected ROC Curve")
        # pylab.show()

        # Compute current area
        area_array[area_index] = auc(selected_fpr, selected_tpr, reorder=True)

        # Update lowest_record_index
        lowest_record_index = highest_record_index

    # Normalize weight distribution and return final score
    weight_distribution = weight_distribution / np.mean(weight_distribution)
    return np.sum(np.multiply(area_array, weight_distribution))

def compute_tpr_with_fpr(y_true, y_score, chosen_fpr=1e-2):
    """Compute the tpr value with the given fpr value.
    
    :param y_true: true binary labels in range {0, 1}
    :type y_true: numpy array
    :param y_score: the probability estimates of the positive class
    :type y_score: numpy array
    :param chosen_fpr: the given fpr value
    :type chosen_fpr: float
    :return: the tpr value
    :rtype: float
    """

    # Compute ROC curve and perform interpolation
    fpr, tpr, _ = roc_curve(y_true, y_score)
    tpr, fpr = perform_interpolation(tpr, fpr, [chosen_fpr])

    # Find the right record
    return tpr[np.argwhere(fpr == chosen_fpr)[0][0]]

def perform_evaluation():
    """Perform evaluation on the submission files."""

    # Read GroundTruth file
    groundtruth_file_path = os.path.join(common.SUBMISSIONS_FOLDER_PATH, common.GROUNDTRUTH_FILE_NAME)
    groundtruth_file_content = pd.read_csv(groundtruth_file_path, skiprows=0).as_matrix()
    groundtruth_label = groundtruth_file_content[:, 1]
    groundtruth_label = groundtruth_label.astype(np.float64)

    # List all csv files in current folder and evaluate them
    submission_file_path_list = glob.glob(os.path.join(common.SUBMISSIONS_FOLDER_PATH, "*.csv"))
    submission_file_path_list = sorted(submission_file_path_list)
    submission_file_name_list = []
    score_list = []
    for submission_file_path in submission_file_path_list:
        if submission_file_path == groundtruth_file_path or "Anonymous" in submission_file_path:
            continue

        # Read current submission file
        submission_file_content = pd.read_csv(submission_file_path, skiprows=0).as_matrix()
        submission_label = submission_file_content[:, 1]

        # Compute Weighted AUC or MCC of current submission file
        score = compute_Weighted_AUC(groundtruth_label, submission_label)
        # score = compute_tpr_with_fpr(groundtruth_label, submission_label)
        # score = compute_MCC(groundtruth_label, submission_label)

        submission_file_name = os.path.basename(submission_file_path)
        print("{} achieved {:.4f}.".format(submission_file_name, score))

        submission_file_name_list.append(submission_file_name)
        score_list.append(score)

    # Print the ranks
    print("\nThe ranks are as follows:")
    ranks = get_ranks(np.array(score_list))
    for current_index in range(len(submission_file_name_list)):
        flag = ranks == (np.max(ranks) - current_index)
        print("{}\t{:.4f}\t{:d}".format(np.array(submission_file_name_list)[flag][0], \
                                        np.array(score_list)[flag][0], current_index + 1))

def combine_submissions():
    """Combine submissions.
    
    :return: the new submission file will be created
    :rtype: None
    """

    facial_image_extension_list = [os.path.splitext(item)[0][1:] for item in prepare_data.FACIAL_IMAGE_EXTENSION_LIST]
    feature_extension_list = [os.path.splitext(item)[0][1:] for item in prepare_data.FEATURE_EXTENSION_LIST]
    classifier_name_list = ["keras", "sklearn"]

    for facial_image_extension, feature_extension, classifier_name in \
        product(facial_image_extension_list, feature_extension_list, classifier_name_list):

        prediction_file_prefix = "Aurora_" + facial_image_extension + "_" + feature_extension + "_" + classifier_name
        submission_file_name_rule = prediction_file_prefix + "_Model_*.csv"
        print("Working on {:s} ...".format(submission_file_name_rule))

        # Read the submission files
        submission_label_list = []
        submission_file_path_list = glob.glob(os.path.join(common.SUBMISSIONS_FOLDER_PATH, submission_file_name_rule))
        for submission_file_path in submission_file_path_list:
            submission_file_content = pd.read_csv(submission_file_path, skiprows=0)
            submission_label = submission_file_content["Prediction"].as_matrix()
            submission_label_list.append(submission_label)

        # Generate the mean submission file
        submission_file_content["Prediction"] = np.mean(submission_label_list, axis=0)
        submission_file_path = os.path.join(common.SUBMISSIONS_FOLDER_PATH,
                                            prediction_file_prefix + "_mean_" + str(int(time.time())) + ".csv")
        submission_file_content.to_csv(submission_file_path, index=False)

        # Generate the median submission file
        submission_file_content["Prediction"] = np.median(submission_label_list, axis=0)
        submission_file_path = os.path.join(common.SUBMISSIONS_FOLDER_PATH,
                                            prediction_file_prefix + "_median_" + str(int(time.time())) + ".csv")
        submission_file_content.to_csv(submission_file_path, index=False)

if __name__ == "__main__":
    # combine_submissions()
    perform_evaluation()
