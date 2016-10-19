import sqlite3 as sqllite
import sys

from flask import Flask, request, render_template
from flask_cors import CORS, cross_origin

from sumy.nlp.stemmers import Stemmer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.edmundson import EdmundsonSummarizer
from sumy.summarizers.kl import KLSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.summarizers.random import RandomSummarizer
from sumy.summarizers.sum_basic import SumBasicSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.utils import get_stop_words

#from flask_restplus import fields
from flask_restplus import Api, Resource, marshal, abort, fields

class ReviewDAL:

    con = None
    cur = None

    def __init__(self):
        self.setup_sql_lite_db()

    def setup_sql_lite_db(self):
        try:

            self.con = sqllite.connect('reviews.db')
            self.cur = self.con.cursor()
            #cur.execute('DROP TABLE IF EXISTS Comment')
            sql = "CREATE TABLE IF NOT EXISTS Review (" \
                  "    id INTEGER PRIMARY KEY AUTOINCREMENT, " \
                  "    assignment_id VARCHAR, " \
                  "    criterion_id VARCHAR, " \
                  "    reviewer_id VARCHAR, " \
                  "    reviewee_id VARCHAR, " \
                  "    score VARCHAR, " \
                  "    feedback VARCHAR)"
            self.cur.execute(sql)
            self.con.commit()

        except sqllite.Error, e:
            print "Error %s:" % e.args[0]
            sys.exit(1)


    def insert_tuples(self, tuples):
        self.cur.executemany("INSERT INTO Review VALUES(NULL, ?, ?, ?, ?, ?, ?)", tuples)
        self.con.commit()


    def insert_reviews(self, assignment_id, criterion_id, reviewer_id, reviewee_id, score, feedback):
        if assignment_id.isdigit and criterion_id.isdigit and reviewer_id.isdigit and reviewee_id.isdigit :
            self.cur.execute("INSERT INTO Review VALUES(NULL, " + str(assignment_id) + ", " + str(criterion_id) + ", " + str(reviewer_id) + ", " +  str(reviewee_id) + "," +  str(score) + ", \'" +feedback + "\')")
        else:
            raise ValueError("All IDs must be number and greater than zero")

    def commit(self):
        self.con.commit()

    def is_record_exist(self, assignment_id, criterion_id=-1, reviewee_id=-1):

        if (criterion_id == -1 and reviewee_id == -1):
            raise Exception("criterion_id & reviewee_id cannot be both empty nor negative")

        if(reviewee_id == -1):
            result = self.get_reviews_by_assignment_criterion(assignment_id, criterion_id)
            return True if len(result)>0 else False
        elif (criterion_id == -1):
            result = self.get_reviews_by_assignment_reviewee(self, assignment_id, reviewee_id)
            return True if result.count()>0 else False
        else:
            result = self.get_reviews_by_assignment_criterion_reviewee(self, assignment_id, criterion_id, reviewee_id)
            return True if result.count()>0 else False


    def get_reviews_by_assignment_criterion(self, assignment_id, criterion_id):

        str_query='SELECT reviewer_id, reviewee_id, score, feedback ' \
                  'FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id + ' ' \
                  'ORDER BY reviewee_id'
        self.cur.execute(str_query)
        rows = self.cur.fetchall()
        return [{"reviewer_id":str(item[0]), "reviewee_id":str(item[1]), "score":str(item[2]), "feedback":str(item[3])} for item in rows]

    def del_reviews_by_assignment_criterion(self, assignment_id, criterion_id):

        str_query='DELETE FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id
        self.cur.execute(str_query)



    def get_reviews_by_assignment_reviewee(self, assignment_id, reviewee_id):

        str_query='SELECT reviewer_id, criterion_id, score, feedback ' \
                  'FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND reviewee = ' + reviewee_id + ' ' \
                  'ORDER BY score'
        self.cur.execute(str_query)
        row = self.cur.fetchall()
        return row

    def del_reviews_by_assignment_reviewee(self, assignment_id, reviewee_id):

        str_query='DELETE FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND reviewee = ' + reviewee_id
        self.cur.execute(str_query)


    def get_reviews_by_assignment_criterion_reviewee(self, assignment_id, reviewee_id, criterion_id ):

        str_query='SELECT reviewer_id, score, feedback ' \
                  'FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id + ' AND reviewee = ' + reviewee_id + ' ' \
                  'ORDER BY score'
        self.cur.execute(str_query)
        return self.cur.fetchall()

    def del_reviews_by_assignment_criterion_reviewee(self, assignment_id, reviewee_id, criterion_id,):

        str_query='DELETE FROM Review ' \
                  'WHERE assignment_id= ' + assignment_id + ' AND criterion_id= ' + criterion_id + ' AND reviewee = ' + reviewee_id
        self.cur.execute(str_query)

class ReviewSummarizer:

    LANGUAGE = "english"
    DEFAULT_ALGORITHM = "textrank"
    DEFAULT_LEN = 10

    def __init__(self):
        self.dal = ReviewDAL()

    def get_summary_generic(self, js, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
            info = self.get_summary_generic_raw(js, length, algorithm)
            return self.merge_summary(info)

    def get_summary_generic_raw(self, js, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
            corpus = ". ".join([item for item in js['sentences']])
            info = self.summarize_with_info(corpus, length, algorithm)
            return info

    def get_summary_by_assignment_criterion_raw(self, aid, cid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        row = self.dal.get_reviews_by_assignment_criterion(aid, cid)
        if len(row) == 0 :
            return ''
        else:
            # comments = [{"reviewer_id":item[0], reviewee_id":item[1], "score":item[2], "feedback":item[3]} for item in row]
            corpus = ". ".join([item['feedback'] for item in row])
            info = self.summarize_with_info(corpus, length, algorithm)
            return info

    def get_summary_by_assignment_criterion(self, aid, cid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
       info = self.get_summary_by_assignment_criterion_raw(aid, cid, length, algorithm)
       return self.merge_summary(info)

    def get_summary_by_assignment_criterion_reviewee_raw(self, aid, cid, sid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        row = self.dal.get_reviews_by_assignment_criterion_reviewee(aid, cid, sid)
        if len(row) == 0 :
            return ''
        else:
            # comments = [{"reviewer_id":item[0], "score":item[1], "feedback":item[2]} for item in row]
            corpus = ". ".join([item['feedback'] for item in row])
            info = self.summarize_with_info(corpus, length, algorithm)
            return info


    def get_summary_by_assignment_criterion_reviewee(self, aid, cid, sid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        info = self.get_summary_by_assignment_criterion_reviewee_raw(aid, cid, sid, length, algorithm)
        return self.merge_summary(info)


    def get_summary_by_assignment_reviewee_raw(self, aid, sid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        row = self.dal.get_reviews_by_assignment_reviewee(aid, sid)
        if len(row) == 0 :
            return ''
        else:
            # comments = [{"reviewer_id":item[0], criterion_id":item[1], "score":item[2], "feedback":item[3]} for item in row]
            corpus = ". ".join([item['feedback'] for item in row])
            info = self.summarize_with_info(corpus, length, algorithm)
            return self.merge_summary(info)

    def get_summary_by_assignment_reviewee(self, aid, sid, length=DEFAULT_LEN, algorithm=DEFAULT_ALGORITHM):
        info = self.get_summary_by_assignment_reviewee_raw( aid, sid, length, algorithm)
        return self.merge_summary(info)

    def summarize_with_info(self, corpus, length, algorithm):
        parser = PlaintextParser.from_string(corpus,Tokenizer(self.LANGUAGE))

        if algorithm == "textrank":
            summarizer = TextRankSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "lexrank":
            summarizer = LexRankSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "luhn":
            summarizer = LuhnSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "edmundson":
            summarizer = EdmundsonSummarizer(Stemmer(self.LANGUAGE))
            summarizer.bonus_words = parser.significant_words
            summarizer.stigma_words = parser.stigma_words
        elif algorithm == "kl":
            summarizer = KLSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "lsa":
            summarizer = LsaSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "sumbasic":
            summarizer = SumBasicSummarizer(Stemmer(self.LANGUAGE))
        elif algorithm == "random":
            summarizer = RandomSummarizer(Stemmer(self.LANGUAGE))
        else:
            raise NotImplemented("Summary algorithm is not available")

        summarizer.stop_words = get_stop_words(self.LANGUAGE)

        return summarizer(parser.document, length)

    def merge_summary(self, text_info):
        return  " ".join([obj.sentence._text for obj in text_info])


app = Flask(__name__)

api = Api(app, version='1.0', title='Summary API',
    description='A simple review summarization API which uses Python\'s sumy library'
)

CORS(app)

app.config.SWAGGER_UI_DOC_EXPANSION = 'list'

ns = api.namespace('sum/v1.0', 'Text Summary v1.0 ')

parser = api.parser()
parser.add_argument('reviews',required=True, location='json', help='Input Format : '
                                                                    '<br>{'
                                                                    '<br>&nbsp;"reviews":[{'
                                                                    '<br>&nbsp;&nbsp;&nbsp;&nbsp;"reviewer_id":"string",'
                                                                    '<br>&nbsp;&nbsp;&nbsp;&nbsp;"reviewee_id":"string",'
                                                                    '<br>&nbsp;&nbsp;&nbsp;&nbsp;"score":"string",'
                                                                    '<br>&nbsp;&nbsp;&nbsp;&nbsp;"feedback":"string"'
                                                                    '<br>&nbsp;&nbsp;}]'
                                                                    '<br>}')

parser_sum = api.parser()
parser_sum.add_argument('sentences', required=True, location='json', help='Input Format :'
                                                                          '<br>{'
                                                                          '<br>&nbsp;"sentences":['
                                                                          '<br>&nbsp;&nbsp;"sentence1"'
                                                                          '<br>&nbsp;]'
                                                                          '<br>}')


###### Definition of data model for documentation
summary_marshaller = api.model('summary',{
    'summary': fields.String(description='Summary of the review')
})

message_marshaller = api.model('message',{
    'message': fields.String(description='Api call status', required=True)
})

review_marshaller = api.model('review',{
    'reviewer_id': fields.String(description='reviewer ID', required=True),
    'reviewee_id': fields.String(description='reviewee ID', required=True),
    'score': fields.String(description='score', required=True),
    'feedback': fields.String(description='textual feedback', required=True)
})

review_list_marshaller = api.model('reviews',{
    'reviews': fields.List(fields.Nested(review_marshaller, description='a list of feedbacks on an assignment')),
})

summary_info_marshaller = api.model('summary_info',{
    'text': fields.String(description='text', required=True),
    'position': fields.String(description='order', required=True),
    'importance': fields.String(description='rating', required=True),
})

summary_info_list_marshaller = api.model('summary_info_list',{
    'summary_info': fields.List(fields.Nested(summary_info_marshaller, description='a list of feedbacks on an assignment with the sentence order and rating information')),
})
###### Definition of data model for documentation

MESSAGE_DOESNT_EXIST = "cannot find record with those ids"
MESSAGE_ADDED = 'reviews added'
MESSAGE_DELETED = 'reviews deleted'
SUPPORTED_ALGORITHMS = ['textrank', 'lexrank', 'luhn', 'edmonson', 'kl', 'lsa', 'sumbasic', 'random']
MESSAGE_ALGORITHM_NOT_SUPPORTED = 'the algorithm you chosed is not supported , please use: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'

########ByAssignmentCriteria
@cross_origin()
@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID'})
class ReviewByAssignmentCriteria(Resource):

    dal = ReviewDAL()

    '''Show a list of reviews on an assignment based on a criteria'''
    @api.marshal_with(review_list_marshaller, code=200)
    def get(self, aid, cid):
        '''Fetch list of reviews on an assignment based on a criteria'''
        results = self.dal.get_reviews_by_assignment_criterion(aid,cid)
        try:
            return {'reviews':results}, 200
        except Exception as e:
            abort(500, message=str(e))

    '''Delete a list of reviews on an assignment based on a criteria'''
    @api.marshal_with(message_marshaller)
    def delete(self, aid, cid):
        '''Delete reviews given assignment id and criterion id'''
        if not self.dal.is_record_exist(aid, criterion_id=cid):
            abort(404, message=MESSAGE_DOESNT_EXIST)
        else:
            self.dal.del_reviews_by_assignment_criterion(aid, cid)
            return {'message':MESSAGE_DELETED}, 200

    '''Add a list of reviews on an assignment based on a criteria'''
    @api.doc(parser=parser, model=review_list_marshaller)
    @api.marshal_with(message_marshaller)
    def post(self, aid, cid):
        '''Update all reviews given assignment id and criterion id'''
        try:
            js = request.get_json()
            tuples = [(aid, cid, row["reviewer_id"],row["reviewee_id"], row["score"], row["feedback"]) for row in js["reviews"]]
            self.dal.insert_tuples(tuples)
        except Exception as e:
            abort(500, message=str(e))
        return {'message':MESSAGE_ADDED}, 200

@cross_origin()
@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summary')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID'})
class SummaryByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()


    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid):
        '''Summarize reviews given assignment id and criterion id'''
        results = self.sum.get_summary_by_assignment_criterion(aid, cid)
        try:
            return {'summary':results}, 200
        except Exception as e:
             abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summaryinfo')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID'})
class SummaryInfoByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_info_list_marshaller)
    def get(self, aid, cid):
        '''Summarize reviews given assignment id and criterion id'''
        results = self.sum.get_summary_by_assignment_criterion_raw(aid, cid)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info}, 200
        except Exception as e:
             abort(500, message=str(e))
@cross_origin()
@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summary/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary'})
class SummaryLengthByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid, length):
        '''Summarize reviews given assignment id, criterion id, and length of the summary'''
        results = self.sum.get_summary_by_assignment_criterion(aid, cid, length=length)
        try:
            return {'summary':results},  200
        except Exception as e:
             abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summaryinfo/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary'})
class SummaryInfoLengthByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_info_list_marshaller)
    def get(self, aid, cid, length):
        '''Summarize reviews given assignment id, criterion id, and length of the summary'''
        results = self.sum.get_summary_by_assignment_criterion_raw(aid, cid, length)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
             abort(500, message=str(e))
@cross_origin()
@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summary/<int:length>/<string:algorithm>')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryLengthAlgorithmByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid, length, algorithm):
        '''Summarize reviews given assignment id, criterion id, length of the summary, and algorithm to use'''
        alg = str(algorithm).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            abort(404, message=MESSAGE_ALGORITHM_NOT_SUPPORTED)

        results = self.sum.get_summary_by_assignment_criterion(aid, cid, length=length, algorithm=alg)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))       

@ns.route('/assignment/<string:aid>/criterion/<string:cid>/reviews/summaryinfo/<int:length>/<string:algorithm>')
@api.doc(params={'aid': 'The assignment ID', 'cid': 'The criteria ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryLengthAlgorithmByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_info_list_marshaller)
    def get(self, aid, cid, length, algorithm):
        '''Summarize reviews given assignment id, criterion id, length of the summary, and algorithm to use'''
        alg = str(algorithm).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            abort(404, message=MESSAGE_ALGORITHM_NOT_SUPPORTED)

        results = self.sum.get_summary_by_assignment_criterion_raw(aid, cid, length=length, algorithm=alg)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))



#########ByAssignmentReviewee
@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID'})
class ReviewByAssignmentReviewee(Resource):
    dal = ReviewDAL()

    '''Show a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(review_list_marshaller, code=200)
    def get(self, aid, sid):
        '''Fetch reviews given assignment id and reviewee id'''
        results = self.dal.get_reviews_by_assignment_reviewee(aid,sid)
        try:
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

    '''Delete a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(message_marshaller)
    def delete(self, aid, sid):
        '''Delete reviews given assignment id and reviewee id'''
        if not self.dal.is_record_exist(aid, reviewee_id=sid):
            abort(404, message=MESSAGE_DOESNT_EXIST)
        else:
            self.dal.del_reviews_by_assignment_criterion(aid, sid)
            return {'message':MESSAGE_DELETED}, 200

    '''Add a list of reviews on an assignment based on a reviewee'''
    @api.doc(parser=parser)
    @api.marshal_with(message_marshaller)
    def post(self, aid, sid):
        '''Add all reviews given assignment id and reviewee id'''
        try:
            js = request.get_json()
            tuples = [(aid, sid, row["reviewer_id"],row["criterion_id"], row["score"], row["feedback"]) for row in js["reviews"]]
            self.dal.insert_tuples(tuples)
        except Exception as e:
            abort(500, message=str(e))
        return {'message':MESSAGE_ADDED}, 200

@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summary')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID'})
class SummaryByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.marshal_with(summary_marshaller)
    @api.doc(description='aid and cid should be unique')
    def get(self, aid, sid):
        '''Summarize reviews given assignment id and reviewee id'''
        results = self.sum.get_summary_by_assignment_reviewee(aid, sid)
        try:
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summaryinfo')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID'})
class SummaryInfoByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.marshal_with(summary_marshaller)
    @api.doc(description='aid and cid should be unique')
    def get(self, aid, sid):
        '''Summarize reviews given assignment id and reviewee id'''
        results = self.sum.get_summary_by_assignment_reviewee_raw(aid, sid)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summary/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'length': 'Length of the summary'})
class SummaryLengthByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and sid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, len):
        '''Summarize reviews given assignment id, reviewee id and length of the summary'''
        results = self.sum.get_summary_by_assignment_reviewee(aid, sid, length=len)
        try:
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summaryinfo/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'length': 'Length of the summary'})
class SummaryInfoLengthByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and sid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, len):
        '''Summarize reviews given assignment id, reviewee id and length of the summary'''
        results = self.sum.get_summary_by_assignment_reviewee_raw(aid, sid, length=len)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))


@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summary/<int:length>/<string:algorithm>')
@api.response(404, 'Algorithm not found')
@api.response(200, 'Succeed executing the command')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryLengthAlgorithmByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid, len, alg):
        '''Summarize reviews given assignment id, reviewee id, and length of the summary'''
        alg = str(alg).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            return marshal({'message':MESSAGE_ALGORITHM_NOT_SUPPORTED}, message_marshaller), 404

        results = self.sum.get_summary_by_assignment_criterion(aid, cid, length=len, algorithm=alg)
        try:
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/reviews/summaryinfo/<int:length>/<string:algorithm>')
@api.response(404, 'Algorithm not found')
@api.response(200, 'Succeed executing the command')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryInfoLengthAlgorithmByAssignmentReviewee(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, cid, len, alg):
        '''Summarize reviews given assignment id, reviewee id, and length of the summary'''
        alg = str(alg).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            return marshal({'message':MESSAGE_ALGORITHM_NOT_SUPPORTED}, message_marshaller), 404

        results = self.sum.get_summary_by_assignment_criterion_raw(aid, cid, length=len, algorithm=alg)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))

##########ByAssignmentRevieweeCriteria
@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews')
@api.response(404, 'reviews not found')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The reviewee ID', 'cid': 'The criterion ID'})
class ReviewByAssignmentRevieweeCriteria(Resource):
    dal = ReviewDAL()

    '''Show a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(review_list_marshaller, code=200)
    def get(self, aid, sid, cid):
        '''Fetch reviews given assignment id, reviewee id, and criterion id'''
        results = self.dal.get_reviews_by_assignment_criterion_reviewee(aid, sid, cid)
        try:
            return {'reviews':results}, 200
        except Exception as e:
            abort(500, message=str(e))

    '''Delete a list of reviews on an assignment based on a reviewee'''
    @api.marshal_with(message_marshaller)
    def delete(self, aid, sid, cid):
        '''Delete reviews given assignment id, reviewee id, and criterion id'''
        if not self.dal.is_record_exist(aid, reviewee_id=sid, criterion_id=cid):
            abort(404, message=MESSAGE_DOESNT_EXIST)
        else:
            self.dal.del_reviews_by_assignment_criterion_reviewee(aid, sid, cid)
            return {'message':MESSAGE_DELETED}, 200

    '''Add a list of reviews on an assignment based on a reviewee'''
    @api.doc(parser=parser)
    @api.marshal_with(message_marshaller)
    def post(self, aid, sid, cid):
        '''Add all reviews given assignment id, reviewee id, and criterion id'''
        try:
            js = request.get_json()
            tuples = [(aid, sid, cid, row["reviewer_id"], row["score"], row["feedback"]) for row in js["reviews"]]
            self.dal.insert_tuples(tuples)
        except Exception as e:
            return abort(500, message=str(e))
        return {'message':MESSAGE_ADDED}, 200

@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summary')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'reviewee_id', 'cid': 'The criteria ID'})
class SummaryByAssignmentRevieweeCriteria(Resource):

    sum = ReviewSummarizer()
    @api.marshal_with(summary_marshaller)
    @api.doc(description='aid, sid, cid should be unique')
    def get(self, aid, sid, cid):
        '''Summarize reviews given assignment id, reviewee id and criterion id'''
        results = self.sum.get_summary_by_assignment_criterion_reviewee(aid, cid, sid)
        try:
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summaryinfo')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'reviewee_id', 'cid': 'The criteria ID'})
class SummaryInfoByAssignmentRevieweeCriteria(Resource):

    sum = ReviewSummarizer()
    @api.marshal_with(summary_marshaller)
    @api.doc(description='aid, sid, cid should be unique')
    def get(self, aid, sid, cid):
        '''Summarize reviews given assignment id, reviewee id and criterion id'''
        results = self.sum.get_summary_by_assignment_criterion_reviewee_raw(aid, cid, sid)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summary/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The criteria ID',  'cid': 'Criterion ID', 'length': 'Length of the summary'})
class SummaryLengthByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, cid, length):
        '''Summarize reviews given assignment id, reviewee id, criterion id, and length of the summary'''
        results = self.sum.get_summary_by_assignment_criterion_reviewee(aid,cid,sid, length=length)
        try:
            return marshal({'summary':results}, summary_marshaller), 200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summaryinfo/<int:length>')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The criteria ID',  'cid': 'Criterion ID', 'length': 'Length of the summary'})
class SummaryInfoLengthByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, cid, length):
        '''Summarize reviews given assignment id, reviewee id, criterion id, and length of the summary'''
        results = self.sum.get_summary_by_assignment_criterion_reviewee_raw(aid,cid,sid, length=length)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summary/<length>/<algorithm>')
@api.response(404, 'Assignment not found')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The criteria ID', 'cid': 'The criteria ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryLengthAlgorithmByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, cid, length, algorithm):
        '''Summarize reviews given assignment id, reviewee id, criterion id, and length of the summary'''
        alg = str(algorithm).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            return marshal({'message':MESSAGE_ALGORITHM_NOT_SUPPORTED}, message_marshaller), 404

        results = self.sum.get_summary_by_assignment_criterion_reviewee(aid,cid,sid, length=length, algorithm=alg)
        try:
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@ns.route('/assignment/<string:aid>/reviewee/<string:sid>/criterion/<string:cid>/reviews/summaryinfo/<length>/<algorithm>')
@api.response(404, 'Assignment not found')
@api.doc(params={'aid': 'The assignment ID', 'sid': 'The criteria ID', 'cid': 'The criteria ID', 'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryInfoLengthAlgorithmByAssignmentCriteria(Resource):

    sum = ReviewSummarizer()

    @api.doc(description='aid and cid should be unique')
    @api.marshal_with(summary_marshaller)
    def get(self, aid, sid, cid, length, algorithm):
        '''Summarize reviews given assignment id, reviewee id, criterion id, and length of the summary'''
        alg = str(algorithm).lower()
        if not alg in SUPPORTED_ALGORITHMS:
            return marshal({'message':MESSAGE_ALGORITHM_NOT_SUPPORTED}, message_marshaller), 404

        results = self.sum.get_summary_by_assignment_criterion_reviewee(aid,cid,sid, length=length, algorithm=alg)
        summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
        try:
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/summary')
class GenericSummary(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser_sum)
    @api.marshal_with(summary_marshaller)
    def post(self):
        '''Summarize a given set of sentences'''
        try:
            js = request.get_json()
            results = self.sum.get_summary_generic(js)
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/summaryinfo')
class GenericSummaryInfo(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser_sum)
    @api.marshal_with(summary_marshaller)
    def post(self):
        '''Summarize a given set of sentences'''
        try:
            js = request.get_json()
            results = self.sum.get_summary_generic_raw(js)
            summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/summary/<length>')
@api.doc(params={'length': 'Length of the summary'})
class SummaryLen(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser_sum)
    @api.marshal_with(summary_marshaller)
    def post(self, length):
        '''Summarize a given set of sentences and length of the summary'''
        try:
            js = request.get_json()
            results = self.sum.get_summary_generic(js, length=length)
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/summaryinfo/<length>')
@api.doc(params={'length': 'Length of the summary'})
class SummaryInfoLen(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser_sum)
    @api.marshal_with(summary_marshaller)
    def post(self, length):
        '''Summarize a given set of sentences and length of the summary'''
        try:
            js = request.get_json()
            results = self.sum.get_summary_generic(js, length=length)
            summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
            return {'summary_info':summary_info},  200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/summary/<length>/<algorithm>')
@api.doc(params={'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryLenAlg(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser_sum)
    @api.marshal_with(summary_marshaller)
    def post(self, length, algorithm):
        '''Summarize a given set of sentences, length of the summar, and type of algorithm'''
        try:
            js = request.get_json()
            results=self.sum.get_summary_generic(js, length, algorithm)
            return {'summary':results}, 200
        except Exception as e:
            abort(500, message=str(e))

@cross_origin()
@ns.route('/summaryinfo/<length>/<algorithm>')
@api.doc(params={'length': 'Length of the summary', 'algorithm': 'summarization algorithm, please choose on of these: textrank, lexrank, luhn, edmonson, kl, lsa, sumbasic, random'})
class SummaryInfoLenAlg(Resource):

    sum = ReviewSummarizer()

    @api.doc(parser=parser_sum)
    @api.marshal_with(summary_marshaller)
    def post(self, length, algorithm):
        '''Summarize a given set of sentences, length of the summar, and type of algorithm'''
        try:
            js = request.get_json()
            results=self.sum.get_summary_generic(js, length, algorithm)
            summary_info = [{'text': obj.sentence._text, 'position': obj.order, 'importance': obj.rating } for obj in results]
            return {'summary_info':summary_info},  200

        except Exception as e:
            abort(500, message=str(e))


@app.route('/developer')
def developer():
    return render_template("developer.html")

@app.route('/instructor')
def instructor():
    return render_template("instructor.html")


if __name__ == '__main__':
    app.run(host= '0.0.0.0', port=3004)



