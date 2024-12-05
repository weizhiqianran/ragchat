from typing import List
import numpy as np
import bcrypt

from ..functions.reading_functions import ReadingFunctions
from ..functions.embedding_functions import EmbeddingFunctions
from ..functions.indexing_functions import IndexingFunctions
from ..functions.chatbot_functions import ChatbotFunctions


class Authenticator:
    def __init__(self):
        pass

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


class Processor:
    def __init__(
        self,
    ):
        self.ef = EmbeddingFunctions()
        self.rf = ReadingFunctions()
        self.indf = IndexingFunctions()
        self.cf = ChatbotFunctions()

    def create_index(self, embeddings: np.ndarray, index_type: str = "flat"):
        if index_type == "flat":
            index = self.indf.create_flat_index(embeddings=embeddings)
        return index

    def filter_search(
        self, domain_content: dict, domain_embeddings: np.ndarray, file_ids: list
    ):
        filtered_indexes = []
        filtered_content = []

        for i, content in enumerate(domain_content):
            if content[4] in file_ids:
                filtered_indexes.append(i)
                filtered_content.append(content)

        filtered_embeddings = domain_embeddings[filtered_indexes]

        index = self.create_index(embeddings=filtered_embeddings)
        boost_info = self.extract_boost_info(
            domain_content=filtered_content, embeddings=filtered_embeddings
        )

        try:
            index_header = self.create_index(embeddings=boost_info["header_embeddings"])
        except IndexError:
            index_header = None

        return index, filtered_content, boost_info, index_header

    def search_index(
        self,
        user_query: str,
        domain_content: dict,
        boost_info: dict,
        index,
        index_header,
    ):
        queries = self.query_preprocessing(user_query=user_query)
        if not queries:
            return None, None, None

        intention = queries[-1]
        query_embeddings = self.ef.create_embeddings_from_sentences(
            sentences=queries[:-1]
        )
        boost_array = self._create_boost_array(
            header_indexes=boost_info["header_indexes"],
            sentence_amount=index.ntotal,
            query_vector=query_embeddings[0],
            index_header=index_header,
        )

        # Get search distances with occurrences
        dict_resource = {}
        for i, query_embedding in enumerate(query_embeddings):
            D, I = index.search(query_embedding.reshape(1, -1), len(domain_content))  # noqa: E741
            if i == 0:
                convergence_vector, distance_vector = I[0], D[0]
            for i, match_index in enumerate(I[0]):
                if match_index in dict_resource:
                    dict_resource[match_index].append(D[0][i])
                else:
                    dict_resource[match_index] = [D[0][i]]

        file_boost_array = self._create_file_boost_array(
            domain_content=domain_content,
            distance_vector=distance_vector,
            convergence_vector=convergence_vector,
        )

        # Combine boost arrays
        combined_boost_array = 0.25 * file_boost_array + 0.75 * boost_array

        # Get average occurrences
        dict_resource = self._avg_resources(dict_resource)
        for key in dict_resource:
            dict_resource[key] *= combined_boost_array[key]
        sorted_dict = dict(
            sorted(dict_resource.items(), key=lambda item: item[1], reverse=True)
        )
        indexes = np.array(list(sorted_dict.keys()))
        sorted_sentence_indexes = indexes[:10]
        resources = self._extract_resources(
            sentence_indexes=sorted_sentence_indexes, domain_content=domain_content
        )

        # Sentences to context creation
        context, context_windows, resources = self.context_creator(
            sentence_index_list=sorted_sentence_indexes,
            domain_content=domain_content,
            header_indexes=boost_info["header_indexes"],
            table_indexes=boost_info["table_indexes"],
        )

        answer = self.cf.response_generation(
            query=user_query, context=context, intention=intention
        )

        return answer, resources, context_windows

    def query_preprocessing(self, user_query):
        generated_queries = self.cf.query_generation(query=user_query).split("\n")

        if len(generated_queries) > 1:
            return generated_queries
        return None

    def _create_boost_array(
        self,
        header_indexes: list,
        sentence_amount: int,
        query_vector: np.ndarray,
        index_header,
    ):
        boost_array = np.ones(sentence_amount)
        if not index_header:
            return boost_array
        D, I = index_header.search(query_vector.reshape(1, -1), 10)  # noqa: E741
        filtered_header_indexes = [
            header_index
            for index, header_index in enumerate(I[0])
            if D[0][index] > 0.30
        ]
        if not filtered_header_indexes:
            return boost_array
        else:
            for i, filtered_index in enumerate(filtered_header_indexes):
                try:
                    start = header_indexes[filtered_index] + 1
                    end = header_indexes[filtered_index + 1]
                    if i > 2:
                        boost_array[start:end] *= 1.1
                    elif i > 0:
                        boost_array[start:end] *= 1.2
                    else:
                        boost_array[start:end] *= 1.3
                except IndexError as e:
                    print(f"List is out of range {e}")
                    continue
            return boost_array

    # File boost function
    def _create_file_boost_array(
        self,
        domain_content: list,
        distance_vector: np.ndarray,
        convergence_vector: np.ndarray,
    ):
        boost_array = np.ones(len(domain_content))
        sort_order = np.argsort(convergence_vector)
        sorted_scores = distance_vector[sort_order]
        file_counts = {}

        if not domain_content:
            return boost_array
        else:
            for _, _, _, _, _, filename in domain_content:
                file_counts[filename] = file_counts.get(filename, 0) + 1

            file_sentence_counts = np.cumsum([0] + list(file_counts.values()))

            for i in range(len(file_sentence_counts) - 1):
                start, end = file_sentence_counts[i], file_sentence_counts[i + 1]
                if np.mean(sorted_scores[start:end]) > 0.30:
                    boost_array[start:end] *= 1.1

        return boost_array

    def context_creator(
        self,
        sentence_index_list: list,
        domain_content: List[tuple],
        header_indexes: list,
        table_indexes: list,
    ):
        context = ""
        context_windows = []
        widened_indexes = []

        for i, sentence_index in enumerate(sentence_index_list):
            window_size = 4 if i < 3 else 2
            start = max(0, sentence_index - window_size)
            end = min(len(domain_content) - 1, sentence_index + window_size)

            if table_indexes:
                for table_index in table_indexes:
                    if sentence_index == table_index:
                        widened_indexes.append((table_index, table_index))
                        table_indexes.remove(table_index)
                        break

            if not header_indexes:
                widened_indexes.append((start, end))
            else:
                for i, current_header in enumerate(header_indexes):
                    if sentence_index == current_header:
                        start = max(0, sentence_index)
                        if (
                            i + 1 < len(header_indexes)
                            and abs(sentence_index - header_indexes[i + 1]) <= 20
                        ):
                            end = min(
                                len(domain_content) - 1, header_indexes[i + 1] - 1
                            )
                        else:
                            end = min(
                                len(domain_content) - 1, sentence_index + window_size
                            )
                        break
                    elif (
                        i + 1 < len(header_indexes)
                        and current_header < sentence_index < header_indexes[i + 1]
                    ):
                        start = (
                            current_header
                            if abs(sentence_index - current_header) <= 20
                            else max(0, sentence_index - window_size)
                        )
                        end = (
                            header_indexes[i + 1] - 1
                            if abs(header_indexes[i + 1] - sentence_index) <= 20
                            else min(
                                len(domain_content) - 1, sentence_index + window_size
                            )
                        )
                        break
                    elif (
                        i == len(header_indexes) - 1
                        and current_header >= sentence_index
                    ):
                        start = (
                            max(0, sentence_index)
                            if abs(current_header - sentence_index) <= 20
                            else max(0, sentence_index - window_size)
                        )
                        end = min(len(domain_content) - 1, sentence_index + window_size)
                        break
                if (start, end) not in widened_indexes:
                    widened_indexes.append((start, end))

        merged_truples = self.merge_tuples(widen_sentences=widened_indexes)

        used_indexes = [
            min(index for index in sentence_index_list if tuple[0] <= index <= tuple[1])
            for tuple in merged_truples
        ]
        resources = self._extract_resources(
            sentence_indexes=used_indexes, domain_content=domain_content
        )

        for i, tuple in enumerate(merged_truples):
            if tuple[0] == tuple[1]:
                windened_sentence = " ".join(domain_content[tuple[0]][0])
                context += f"Context{i+1}: File:{resources['file_names'][i]}, Confidence:{(len(sentence_index_list)-i)/len(sentence_index_list)}, Table\n{windened_sentence}\n"
                context_windows.append(windened_sentence)
            else:
                windened_sentence = " ".join(
                    domain_content[index][0] for index in range(tuple[0], tuple[1])
                )
                context += f"Context{i+1}: File:{resources['file_names'][i]}, Confidence:{(len(sentence_index_list)-i)/len(sentence_index_list)}, {windened_sentence}\n\n"
                context_windows.append(windened_sentence)

        return context, context_windows, resources

    def _avg_resources(self, resources_dict):
        for key, value in resources_dict.items():
            value_mean = sum(value) / len(value)
            value_coefficient = value_mean + len(value) * 0.0025
            resources_dict[key] = value_coefficient
        return resources_dict

    def _extract_resources(self, sentence_indexes: list, domain_content: List[tuple]):
        resources = {"file_names": [], "page_numbers": []}
        for index in sentence_indexes:
            resources["file_names"].append(domain_content[index][5])
            resources["page_numbers"].append(domain_content[index][3])
        return resources

    def _create_dynamic_context(self, sentences):
        context = ""
        for i, sentence in enumerate(sentences):
            context += f"{i + 1}: {sentence}\n"
        return context

    def extract_boost_info(self, domain_content: List[tuple], embeddings: np.ndarray):
        boost_info = {
            "header_indexes": [],
            "headers": [],
            "header_embeddings": [],
            "table_indexes": [],
        }
        for index in range(len(domain_content)):
            if domain_content[index][1]:
                boost_info["header_indexes"].append(index)
                boost_info["headers"].append(domain_content[index][0])

            if domain_content[index][2]:
                boost_info["table_indexes"].append(index)
        boost_info["header_embeddings"] = embeddings[boost_info["header_indexes"]]
        return boost_info

    def merge_tuples(self, widen_sentences):
        indexed_tuples = sorted(enumerate(widen_sentences), key=lambda x: x[1][0])

        merged_groups = []
        current_group = {
            "start_index": indexed_tuples[0][0],
            "tuple": indexed_tuples[0][1],
            "indices": [indexed_tuples[0][0]],
        }

        for index, current_tuple in indexed_tuples[1:]:
            if current_tuple[0] <= current_group["tuple"][1] + 1:
                current_group["tuple"] = (
                    min(current_group["tuple"][0], current_tuple[0]),
                    max(current_group["tuple"][1], current_tuple[1]),
                )
                current_group["indices"].append(index)
            else:
                merged_groups.append(current_group)
                current_group = {
                    "start_index": index,
                    "tuple": current_tuple,
                    "indices": [index],
                }
        merged_groups.append(current_group)

        result = widen_sentences.copy()
        for group in merged_groups:
            min_index = min(group["indices"])
            result[min_index] = group["tuple"]
            for idx in group["indices"]:
                if idx != min_index:
                    result[idx] = None

        merged_result = [x for x in result if x is not None]

        return merged_result
