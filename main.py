from loguru import logger
from utils import pwdEncrypt, searchCollegeByName, getCaptcha, login, logout, getUserIndex, getActivities, recordQuestion, startPaper, preparePaper, getNear, submitPaper, index, preparePaperPractice, startPaperPractice, submitPaperPractice, recordQuestionPractice
from dbProcess import request_data, insert_data, count_questions, count_legacy, DB_FILE
import requests
import json
import time
import os
from tqdm import tqdm
Headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}
nameUnset = False
MISSING_FILE = "missing_questions.json"
WRONG_ANSWER = "1505a534-ddd6-48bb-91b9-d92d7d03fb30" # 占位错误答案：好得不能再好的判错用的选项

def isSuccess(res):
    return isinstance(res, dict) and (res.get("status") == 200 or res.get("code") == 200)

def isUnauthorized(res):
    return isinstance(res, dict) and res.get("code") == 401

def apiMessage(res):
    if isinstance(res, dict):
        return res.get("message", res)
    return res

def pickWrongAnswer(question, rightAnswer):
    # 知道正确答案时挑本卷内确定错的选项；不知道时用占位错答，保证这道题不得分
    if rightAnswer is None:
        return WRONG_ANSWER
    rightIds = set(rightAnswer.split(","))
    for option in question["optionList"]:
        if option["id"] not in rightIds:
            return option["id"]
    return question["optionList"][0]["id"]

def submitAnswer(token, questionId, activityId, useTime, answerIds):
    for attempt in range(0,2):
        try:
            return json.loads(recordQuestion(token,questionId,activityId,useTime,answerIds))
        except:
            logger.warning("网络问题导致答案未能如愿提交，如多次出现，请检查网络环境或使用热点！正在重试...")
    return None

def pickPracticeMode(activityName, choiceIndex):
    # 各校任务列表的顺序不一致，优先按任务名称判断类型，判断不出来再退回旧版按序号的规则
    if any(key in activityName for key in ("练习", "刷题", "闯关")):
        return True
    if any(key in activityName for key in ("考试", "考核", "模拟")):
        return False
    logger.warning("无法由任务名称判断类型，按旧规则处理（序号 0/1 视为练习）。")
    return choiceIndex <= 1

def saveMissing(missingList):
    if not missingList:
        return
    history = []
    if os.path.exists(MISSING_FILE):
        try:
            with open(MISSING_FILE, encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    known = {item["id"] for item in history}
    history.extend(item for item in missingList if item["id"] not in known)
    with open(MISSING_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def readInt(prompt, minimum=None, maximum=None):
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            logger.error("请输入整数。")
            continue
        if minimum is not None and value < minimum:
            logger.error("输入值不能小于 %i。" % minimum)
            continue
        if maximum is not None and value > maximum:
            logger.error("输入值不能大于 %i。" % maximum)
            continue
        return value

def runPracticeTask(token, activityId):
    logger.info("进入练习流程")
    res = json.loads(preparePaperPractice(token, activityId))
    if not isSuccess(res):
        logger.error("创建练习失败：%s" % apiMessage(res))
        return False
    res = json.loads(startPaperPractice(token, activityId))
    if not isSuccess(res):
        logger.error("开始练习失败：%s" % apiMessage(res))
        return False
    learned = 0
    existed = 0
    noAnswer = 0
    for seq in range(0,10):
        res = json.loads(getNear(token, activityId, seq))
        if not isSuccess(res):
            logger.error("第 %i 页题目获取失败：%s" % (seq, apiMessage(res)))
            return False
        logger.info("页面请求：%i/9" % seq)
        for question in tqdm(res["data"]["result"]["questionList"], desc="答题进度"):
            questionId = question["id"]
            answerList = ",".join(option["id"] for option in question["optionList"] if option.get("isCorrect") == 1)
            if answerList:
                state = insert_data(questionId, answerList)
                if state is None:
                    logger.warning("题库写入失败：%s" % questionId)
                elif state:
                    learned += 1
                else:
                    existed += 1
            else:
                noAnswer += 1
            res = json.loads(recordQuestionPractice(token, questionId, activityId, 10, seq, answerList))
            if isUnauthorized(res):
                logger.error("账号登录失效！")
                return False
            if not isSuccess(res):
                logger.error("练习答案提交失败：%s" % apiMessage(res))
                return False
    res = json.loads(submitPaperPractice(token, activityId))
    if not isSuccess(res):
        logger.error("答题提交失败：%s" % apiMessage(res))
        return False
    logger.info("答题提交成功！")
    logger.info(f"状态：{res['data']['result']['passedLabel']}，分数：{res['data']['result']['score']}")
    logger.info("本次练习新收录 %i 题，已有 %i 题，题库现有 %i 题。" % (learned, existed, count_questions()))
    if noAnswer:
        logger.warning("有 %i 题接口没有返回正确答案（isCorrect），这些题无法自动收录。" % noAnswer)
    return True

def runExamTask(token, activityId, targetScore, timePerQuestion, showDonation=True):
    logger.info("开始创建考试.")
    logger.info("进入考试流程")
    res = json.loads(preparePaper(token, activityId))
    if not isSuccess(res):
        logger.error("试卷创建失败：%s" % apiMessage(res))
        return False
    result = res["data"]["result"]
    logger.info(f"试卷创建成功，答题机会为{result.get('totalTimes')}次，您已作答{result.get('doneTimes')}次，答题通过分数为{result.get('passScore')}分，程序将在两秒后开始作答。")
    time.sleep(2)
    questionList = json.loads(startPaper(token, activityId))
    if not isSuccess(questionList):
        logger.error("获取试卷数据失败：%s" % apiMessage(questionList))
        return False
    questionList = questionList["data"]["result"]["questionList"]
    if not questionList:
        logger.error("试卷里没有题目，请稍后重试。")
        return False
    logger.info("获取试卷数据，共 %i 题。" % len(questionList))
    hit = 0
    missing = []
    for questionIndex, question in enumerate(questionList, start=1):
        logger.info("正在作答第 %i 题..." % questionIndex)
        questionId = question["id"]
        rows = request_data(questionId)
        rightAnswer = rows[0][1] if rows else None
        if questionIndex <= targetScore:
            if rightAnswer is None:
                missing.append({"id":questionId, "title":question["title"], "options":[{"id":option["id"], "content":option["content"]} for option in question["optionList"]]})
                logger.warning("题库中没有这道题，已记入 %s，本题先用第一个选项试一下。" % MISSING_FILE)
                answer = question["optionList"][0]["id"]
            else:
                hit += 1
                answer = rightAnswer
        else:
            answer = pickWrongAnswer(question, rightAnswer)
        res = submitAnswer(token, questionId, activityId, timePerQuestion, answer)
        if (res is None or not isSuccess(res)) and answer == WRONG_ANSWER and question["optionList"]:
            logger.warning("占位错答没有被接受，改用本卷内的选项重试。")
            res = submitAnswer(token, questionId, activityId, timePerQuestion, question["optionList"][0]["id"])
        if res is None:
            logger.error("提交失败，考试已停止！")
            return False
        if isUnauthorized(res):
            logger.error("账号登录失效，请不要在脚本运行时登陆账号，否则将浪费一次考试机会.")
            return False
        if not isSuccess(res):
            logger.error("本题提交异常，考试已停止：%s" % apiMessage(res))
            return False
        logger.success(f"答案保存成功，等待{timePerQuestion}秒，然后下一题.")
        time.sleep(timePerQuestion)
    saveMissing(missing)
    logger.info("期望正确 %i 题，其中题库命中 %i 题。" % (targetScore, hit))
    if missing:
        logger.warning("本卷有 %i 题不在题库中，命中 %i 题，缺失题目已记入 %s。" % (len(missing), hit, MISSING_FILE))
        logger.warning("建议先跑一遍练习任务把题库补全，再回来考试。")
    res = json.loads(submitPaper(token, activityId))
    if not isSuccess(res):
        logger.error("出错了，错误：%s" % apiMessage(res))
        return False
    logger.success("交卷成功")
    logger.info(f"得分：{res['data']['result']['score']}分，状态：{res['data']['result']['passedLabel']}，用时：{res['data']['result']['useTimeLabel']}")
    if showDonation:
        try:
            os.startfile('donation.jpg') # show my code qwq
        except Exception:
            logger.warning("failed to show my qrcode TAT")
    return True

def runAutomaticTasks(token, activityList, activityNames, mockScore, formalScore, timePerQuestion):
    tasks = [
        ("顺序练习", 0, None),
        ("随机练习", 1, None),
        ("模拟考试", 2, mockScore),
        ("正式考试", 3, formalScore),
    ]
    for expectedName, taskIndex, targetScore in tasks:
        activityId = activityList[taskIndex]
        activityName = activityNames[taskIndex]
        logger.info("开始自动任务：%s（任务列表名称：%s）" % (expectedName, activityName))
        if targetScore is None:
            taskSucceeded = runPracticeTask(token, activityId)
        else:
            taskSucceeded = runExamTask(token, activityId, targetScore, timePerQuestion, showDonation=False)
        if not taskSucceeded:
            logger.error("自动任务失败，已停止后续项目：%s" % expectedName)
            return False
        logger.info("本项任务已完成：%s" % activityName)
    return True

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print("切换到工作目录：", os.getcwd())

logger.info("题库：%s 有 %i 题" % (DB_FILE, count_questions()))

logger.info("正在请求学校列表...")
try:
    schoolList = requests.post("https://mars.mycourse.cn/marsapi/api/login/v1/listTenant",headers=Headers).text
except Exception:
    logger.error("网络错误。")
    input("网络错误，程序异常结束。")
    exit()

schoolList = json.loads(schoolList)
logger.info("学校清单载入完成，请输入学校名称：")
inSchoolName = input("请输入学校名称[支持关键词]：")
schoolCode = searchCollegeByName(inSchoolName, schoolList)
logger.info("完成学校选择：%s" % schoolCode)
logger.info("请输入用户名")
username = input("请输入用户名：")
logger.info("请输入密码")
password = input("请输入密码：")
password = pwdEncrypt(password) # MD5 32大
timestamp = str(int(time.time() * 1000))
logger.info("给用户投喂验证码...")
def killCaptcha(timestamp):
    getCaptcha(timestamp)
    os.startfile("captcha.png")
    res = input("请输入您看到的验证码，如果没有自动打开，请前往程序所在目录下打开captcha.png查看")
    return res

captcha = killCaptcha(timestamp)
# try:
#     status = getCaptcha(timestamp)
# except:
#     logger.error("验证码处理失败！[如果您使用的是.exe版本，请尝试运行源代码]")
#     input("验证码处理失败，程序退出。")
#     exit()
# if status == True:
#     captcha = input("请输入验证码[按回车键刷新]：")
# else:
#     captcha = input("请打开文件夹中的captcha文件并输入验证码[按回车键刷新]：")
# while captcha == "":
#     logger.info("验证码已刷新.")
#     timestamp = str(int(time.time() * 1000))
#     status = getCaptcha(timestamp)
#     if status == True:
#         captcha = input("请输入验证码[按回车键刷新]：")
#     else:
#         captcha = input("请打开文件夹中的captcha文件并输入验证码[按回车键刷新]：")

def main_login(schoolCode, username, password, captcha, timestamp):
    logger.info("OK，正在进行登录流程...")
    res = json.loads(login(tenant=schoolCode, username=username,passwordE=password,captcha=captcha,timestamp=timestamp))
    userData = json.loads(getUserIndex())
    return res, userData

res, userData = main_login(schoolCode, username, password, captcha, timestamp)
while True:
    if res['success'] == False and "验证码错误" in res["message"]:
        logger.warning("验证码错误，正在重新尝试")
        timestamp = str(int(time.time() * 1000))
        newCaptcha = killCaptcha(timestamp)
        res = json.loads(login(tenant=schoolCode, username=username,passwordE=password,captcha=newCaptcha,timestamp=timestamp))
    else:
        break

if res["success"] == True:
    try:
        logger.success("登录成功，你好，%s ！" % res["data"]["result"]["realName"])
        userName = res["data"]["result"]["realName"]
    except KeyError:
        logger.warning("学校未配置学生姓名.")
        logger.success("登录成功！")
        nameUnset = True
else:
    logger.error(res["message"])
    logger.error("登陆失败，请重新运行脚本！")
    input()
    exit()

token = res["data"]["result"]["token"]
activities = json.loads(getActivities(token))
activityList = []
activityNames = []
for _ in activities["data"]["result"]["studyActivityList"]:
    activityList.append(_["userActivityId"])
    activityNames.append(_["name"])
logger.info("部分学校要求先完成模拟考试，然后再完成正式考试，若没有正式考试选项，可能是学校暂未开放，请与学校发布信息核实。")
logger.warning("脚本运行期间请不要登录！！！")
logger.warning("脚本运行期间请不要登录！！！")
logger.warning("脚本运行期间请不要登录！！！")
automaticModeUsed = False
while True:
    for index, name in enumerate(activityNames):
        logger.info("[%i] %s" % (index, name))
    logger.info("[A] 自动连续完成四个项目")
    raw = input("请选择你要做的任务[输入数字序号，输入 A 自动完成四项，直接回车结束程序]：").strip()
    if raw == "":
        break
    if raw.lower() == "a":
        automaticModeUsed = True
        if len(activityList) < 4:
            logger.error("任务列表不足四项，无法启动自动模式。")
            break
        logger.info("自动模式将依次完成：顺序练习、随机练习、模拟考试、正式考试。")
        mockScore = readInt("请输入模拟考试目标分数[0-100]：", 0, 100)
        formalScore = readInt("请输入正式考试目标分数[0-100]：", 0, 100)
        logger.info("请输入两个考试共用的每题答题间隔")
        logger.info("时长参考：每题6秒->9-10分钟；每题7秒->11分钟；每题8秒->13分钟；每题9秒->15分钟")
        logger.warning("若题目间隔过短，例如1秒，将会被系统判定为无效作答，并浪费一次答题机会！")
        timePerQuestion = readInt("请输入每一题时长(秒)：", 1)
        allSucceeded = runAutomaticTasks(
            token, activityList, activityNames, mockScore, formalScore, timePerQuestion
        )
        if allSucceeded:
            logger.success("四个项目已全部完成。")
        break
    if not raw.isdigit() or int(raw) >= len(activityList):
        logger.error("请输入列表里的数字序号或 A。")
        continue
    choice = int(raw)
    activityId = activityList[choice]
    activityName = activityNames[choice]
    practiceMode = pickPracticeMode(activityName, choice)
    logger.info("任务识别为：%s" % ("练习" if practiceMode else "考试"))
    if practiceMode:
        taskSucceeded = runPracticeTask(token, activityId)
    else:
        logger.info("请输入期望分数")
        targetScore = readInt("请输入期望分数[0-100]：", 0, 100)
        logger.info("请输入每一题时长")
        logger.info("时长参考：每题6秒->9-10分钟；每题7秒->11分钟；每题8秒->13分钟；每题9秒->15分钟")
        logger.warning("若题目间隔过短，例如1秒，将会被系统判定为无效作答，并浪费一次答题机会！")
        timePerQuestion = readInt("请输入每一题时长(秒)：", 1)
        taskSucceeded = runExamTask(token, activityId, targetScore, timePerQuestion)
    if not taskSucceeded:
        logger.error("任务执行失败，程序已停止。")
        break
    logger.info("本项任务已完成：%s" % activityName)
logger.success("程序完全结束.")
res = json.loads(logout())
if nameUnset == True:
    logger.success(f"登出成功，感谢使用！")
else:
    logger.success(f"登出成功，{userName}，感谢使用！")

if not automaticModeUsed:
    input()

