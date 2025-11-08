from loguru import logger
from utils import pwdEncrypt, searchCollegeByName, getCaptcha, login, logout, getUserIndex, getActivities, recordQuestion, startPaper, preparePaper, getNear, submitPaper, index, preparePaperPractice, startPaperPractice, submitPaperPractice, recordQuestionPractice
from dbProcess import request_data
import requests
import json
import time
import os
from tqdm import tqdm
Headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}
nameUnset = False

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print("切换到工作目录：", os.getcwd())

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
logger.info("处理验证码...")
timestamp = str(int(time.time() * 1000))
try:
    status = getCaptcha(timestamp)
except:
    logger.error("验证码处理失败！[如果您使用的是.exe版本，请尝试运行源代码]")
    input("验证码处理失败，程序退出。")
    exit()
if status == True:
    captcha = input("请输入验证码[按回车键刷新]：")
else:
    captcha = input("请打开文件夹中的captcha文件并输入验证码[按回车键刷新]：")
while captcha == "":
    logger.info("验证码已刷新.")
    timestamp = str(int(time.time() * 1000))
    status = getCaptcha(timestamp)
    if status == True:
        captcha = input("请输入验证码[按回车键刷新]：")
    else:
        captcha = input("请打开文件夹中的captcha文件并输入验证码[按回车键刷新]：")
logger.info("OK，正在进行登录流程...")
res = json.loads(login(tenant=schoolCode, username=username,passwordE=password,captcha=captcha,timestamp=timestamp))
userData = json.loads(getUserIndex())
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
___ = 0
for _ in activities["data"]["result"]["studyActivityList"]:
    activityList.append(_["userActivityId"])
    logger.info("[%i] %s" % (___, _["name"]))
    ___ += 1
logger.info("部分学校要求先完成模拟考试，然后再完成正式考试，若没有正式考试选项，可能是学校暂未开放，请与学校发布信息核实。")
choice = int(input("请选择你要刷的任务[输入数字序号]："))
try:
    activityId = activityList[choice]
except Exception:
    logger.error("出错了")
    input()
    exit()
logger.warning("脚本运行期间请不要登录！！！")
logger.warning("脚本运行期间请不要登录！！！")
logger.warning("脚本运行期间请不要登录！！！")
if choice <= 1:
    logger.info("进入练习流程")
    preparePaperPractice(token, activityId)
    startPaperPractice(token, activityId)
    seq = 0
    for seq in range(0,10):
        questionList = json.loads(getNear(token,activityId,seq))
        logger.info("页面请求：%i/9" % seq)
        for _ in tqdm(questionList["data"]["result"]["questionList"], desc="答题进度"):
            questionId = _["id"]
            answerList = ""
            for __ in _["optionList"]:
                if __["isCorrect"] == 1:
                    answerList = answerList + "%s," % __["id"]
                else:
                    pass
            answerList = answerList[0:-1]
            res = json.loads(recordQuestionPractice(token, questionId, activityId, 10, seq, answerList))
            if res["code"] == 401:
                logger.error("账号登录失效！")
                input()
                exit()
        seq += seq
    res = json.loads(submitPaperPractice(token, activityId))
    if res["status"] == 200:
        logger.info("答题提交成功！")
        logger.info(f"状态：{res['data']['result']['passedLabel']}，分数：{res['data']['result']['score']}")
else:
    logger.info("请输入期望分数")
    n = int(input("请输入期望分数："))
    logger.info("请输入每一题时长")
    logger.info("时长参考：每题6秒->9-10分钟；每题7秒->11分钟；每题8秒->13分钟；每题9秒->15分钟")
    logger.warning("若题目间隔过短，例如1秒，将会被系统判定为无效作答，并浪费一次答题机会！")
    time_con = int(input("请输入每一题时长(秒)："))
    logger.info("开始创建考试.")
    logger.info("进入考试流程")
    res = json.loads(preparePaper(token, activityId))
    if res["code"] == 200:
        logger.info(f"试卷创建成功，答题机会为{res['data']['result']['totalTimes']}次，您已作答{res['data']['result']['doneTimes']}次，答题通过分数为{res['data']['result']['passScore']}分，程序将在两秒后开始作答。")
    time.sleep(2)
    questionList = json.loads(startPaper(token, activityId))
    logger.info("获取试卷数据")
    t = 1
    wa = "1505a534-ddd6-48bb-91b9-d92d7d03fb30" # 随便找的一个来充当错误答案
    if questionList["status"] != 200:
        logger.error(f"出错：{questionList['message']}")
    for _ in questionList["data"]["result"]["questionList"]:
        logger.info("正在作答第 %i 题..." % t)
        if t <= n:
            questionId = _["id"]
            answer = request_data(questionId)[0][1]
            try:
                res = json.loads(recordQuestion(token,questionId,activityId,time_con,answer))
            except:
                logger.warning("网络问题导致答案未能如愿提交，如多次出现，请检查网络环境或使用热点！正在重试...")
                try:
                    res = json.loads(recordQuestion(token,questionId,activityId,time_con,answer))
                except:
                    logger.error("提交失败，跳过本题！")
            if res["code"] == 401:
                logger.error("账号登录失效，请不要在脚本运行时登陆账号，否则将浪费一次考试机会.")
                input()
                exit()
            else:
                logger.success(f"正确答案保存成功，等待{time_con}秒，然后下一题.")
        else:
            questionId = _["id"]
            answer = wa
            res = json.loads(recordQuestion(token,questionId,activityId,time_con,answer))
            if res["code"] != 200:
                logger.error(res["message"])
                input()
                exit()
            logger.success(f"错误答案保存成功，等待{time_con}秒，然后下一题.")
        t += 1
        time.sleep(time_con)
    # TODO: 这里可以加一个对答题返回的判断，睡觉去了...
    res = json.loads(submitPaper(token, activityId))
    if res["status"] == 200:
        logger.success("交卷成功")
        logger.info(f"得分：{res['data']['result']['score']}分，状态：{res['data']['result']['passedLabel']}，用时：{res['data']['result']['useTimeLabel']}")
    else:
        logger.error(f"出错了，错误：{res['message']}")
        input()
        exit()
logger.success("程序完全结束.")
res = json.loads(logout())
if nameUnset == True:
    logger.success(f"登出成功，感谢使用！")
else:
    logger.success(f"登出成功，{userName}，感谢使用！")

input()

