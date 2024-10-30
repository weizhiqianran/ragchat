from openai import OpenAI
from dotenv import load_dotenv
from langdetect import detect
import textwrap


class ChatbotFunctions:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI()

    def _prompt_query_generation(self, query, lang):
        if lang == "tr":
            return textwrap.dedent(f"""
            Görev: Önce anlamı sonra yazım hatalarını kontrol edin ve anlamsal olarak benzer 5 soru oluşturun.

            Talimatlar: Size bir kullanıcı sorusu verilir.
            Öncelikle kullanıcı sorusunu kontrol edin, eğer kullanıcı sorusunun anlamı yoksa boş string '' döndürün, soru anlamlıysa şunları yapın:
            Herhangi bir yazım veya dilbilgisi hatası olup olmadığını kontrol edin ve düzeltilmiş soruyu çıktıdaki ilk soru olarak döndürün.
            Ardından, düzeltilmiş soruya anlamsal olarak benzer 5 ek soru oluşturun.
            Oluşturulan soruların kelime kullanımının farklı olmasını ancak orijinal sorunun aynı anlamını veya amacını korumasını sağlayın.
            Çıktıyı **kesinlikle** başka bir metin veya açıklama eklemeden aşağıdaki şablon formatında döndürün:

            [düzeltilmiş soru]
            [birinci anlamsal benzer soru]
            [ikinci anlamsal benzer soru]
            [üçüncü anlamsal benzer soru]
            [dördüncü anlamsal benzer soru]
            [beşinci anlamsal benzer soru]

            Çıktınız tam olarak bu formatı takip etmelidir. Bu şablonun ötesinde hiçbir ek bilgi veya metin eklenmemelidir.
            
            Kullanıcı sorusu: {query}
            """)
        else:
            return textwrap.dedent(f"""
            Task: Check for meaning first then spelling errors and create 5 semantically similar questions.

            Instructions: You are given a user question. 
            First, check the user question, if the user question has no meaning then return empty string '' if question is meaningul do the following:
            Check for any spelling or grammatical errors, and return the corrected question as the first question in the output. 
            Then, generate 5 additional questions that are semantically similar to the corrected question. 
            Ensure that the generated questions vary in wording but retain the same meaning or intent as the original question. 
            Return the output **strictly** in the following template format without any additional text or explanations:

            [corrected question]
            [first semantically similar question]
            [second semantically similar question]
            [third semantically similar question]
            [fourth semantically similar question]
            [fifth semantically similar question]

            Your output should follow this format exactly. No extra information or text should be included beyond this template.
            
            User question: {query}
            """)

    def _prompt_answer_generation(self, query, context, lang):
        if lang == "tr":
            return textwrap.dedent(f"""
            Siz, verilen metinden belirli bilgileri çıkarmada uzmanlaşmış bir yapay zeka asistanısınız.
            Göreviniz, verilen bağlam pencerelerini analiz etmek ve kullanıcının sorgusu temelinde ilgili verileri çıkarmaktır.

            Talimatlar:
            1. Size her biri birkaç cümle içeren ve numaralarla ayırt edilebilen bağlam pencereleri sağlanacaktır. Örneğin 1:, 2: şeklinde.
            2. Tüm bağlam pencerelerini dikkatlice okuyup anlayın.
            3. Kullanıcının sorgusunu analiz ederek ne tür spesifik bilgileri aradığını anlayın.
            4. Hiyerarşiye göre bağlam pencerelerinden ilgili bilgileri arayın ve çıkarın; cevabınız bu önceliği yansıtmalıdır.
            5. Verilen bağlam pencereleri içinde çelişkili bilgiler varsa, her zaman üst bağlam penceresini kullanın (Örneğin, 3 yerine 1).
            6. İstenen bilgi hiçbir bağlam penceresinde mevcut değilse bunu açıkça belirtin.
            7. Çıkardığınız bilgiyi açık ve net bir şekilde sunun.
            8. Yalnızca sağlanan bağlam pencerelerindeki bilgilere odaklanın. Ek bilgi eklemeyin veya açıkça belirtilmeyen varsayımlarda bulunmayın.
            9. Çıkarılan bilgiler maddeler içeriyorsa, yanıtı maddeler halinde ayırarak verin.
            10. Yanıt verdikten sonra bağlam pencerelerindeki bilgileri kullanarak neden-sonuç ilişkisini vurgulayan detaylı bir açıklama hazırlayın.

            Aşağıdaki formatta yanıt verin ve her zaman her ikisini de doldurun:
            I: [Çıkarılan veriyi buraya yazın]
            E: [Açıklamayı buraya yazın]

            Bağlam Pencereleri:
            {context}

            Kullanıcı Sorgusu: {query}
            """)
        else:
            return textwrap.dedent(f"""
            You are an AI assistant specialized in extracting specific information from provided text.
            Your task is to analyze the given context windows and extract relevant data based on the user's query.

            Instructions:
            1. You will be provided with context windows, each containing several sentences and can be differentiated with numbers. Like Context1:, Context2:
            2. Carefully read and understand all of the context windows.
            3. Analyze the user's query to understand what specific information they are looking for.
            4. Search for and extract the relevant information from the context windows according to the hierarchy and ensure your response reflects this priority.
            5. If there are contradictory information within the given context windows, always use the higher context window while generating the answer. (For example Context1 insted of Context3)
            6. If the requested information is not present in any of the context windows, state that clearly.
            7. Present the extracted information in a clear and concise manner.
            8. Remember to focus solely on the information present in the provided context windows. Do not include external knowledge or make assumptions beyond what is explicitly stated.
            9. If the extracted information includes substances give the answer also dividing it into substances.
            10. After giving the answer prepare a detailed explanation with using underline cause effect relationship using the information given in context windows.

            Answer in the following format and always give them both:
            I: [Provide the extracted data here]
            E: [Provide explanation]

            Context Windows:
            {context}

            User Query: {query}
            """)

    def response_generation(self, query, context):
        lang = self.detect_language(query=query)
        prompt = self._prompt_answer_generation(
            query=query,
            context=context,
            lang=lang
        )
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ],
            temperature=0
        )
        answer = response.choices[0].message.content.strip()
        return answer
    
    def query_generation(self, query):
        lang = self.detect_language(query=query)
        prompt = self._prompt_query_generation(
            query,
            lang=lang
        )
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ],
            temperature=0
        )
        new_queries = response.choices[0].message.content.strip()
        return new_queries

    def detect_language(self, query):
        lang = "en"
        try:
            lang = detect(text=query)
            if lang == "tr":
                return lang
            else:
                return "en"
        except:
            return "en"
