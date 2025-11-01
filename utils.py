# 工具类
import hashlib
import requests
import os

Headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}

def pwdEncrypt(text):
    md5 = hashlib.md5()
    md5.update(text.encode('utf-8'))
    return md5.hexdigest().upper()

def searchCollegeByName(collegeName, schoolList):
    # 通过学校名称检索获得学校id
    collegeList = schoolList
    narrowIdList = []
    narrowNameList = []
    for i in collegeList["data"]["result"]:
        if collegeName in i["name"]:
            narrowIdList.append(i["code"])
            narrowNameList.append(i["name"])
    j = 0
    for i in narrowNameList:
        print("[%i] %s" % (j, i))
        j += 1
    if narrowIdList == [] or narrowNameList == []:
        input("程序异常结束：没有检索到学校。【按回车退出】")
        exit()
    if j == 1:
        print("命中.")
        return narrowIdList[0]
    else:
        index = input("学校检索完成，请输入方框内的数字【直接回车以选择第一个】：")
        if index == "":
            index = 0
        try:
            index = int(index)
        except:
            input("程序异常结束：你给程序投喂了奇怪的东西。【按回车退出】")
            exit()
        return narrowIdList[index]

def getCaptcha(timestamp):
    filename = "captcha.png"
    data = {"timestamp":timestamp}
    captcha = requests.get("https://mars.mycourse.cn/marsapi/api/login/v1/getCaptcha?timestamp=%s" % timestamp)
    with open("captcha.png","wb") as f:
        f.write(captcha.content)
    os.startfile("captcha.png")
    return True

def login(tenant, username, passwordE, captcha, timestamp):
    data = {
        "tenantCode":tenant,
        "username":username,
        "encryptedPassword":passwordE,
        "captchaCode":captcha,
        "timestamp":timestamp
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/login/v1/login", data=data, headers=Headers)
    return res.text

def logout():
    res = requests.post("https://mars.mycourse.cn/marsapi/api/login/v1/logout", headers=Headers)
    return res.text

def getUserIndex():
    res = requests.post("https://mars.mycourse.cn/marsapi/api/user/v1/index", headers=Headers)
    return res.text

def getActivities(token):
    Cookies = {"mars_token":token}
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/project/v1/index", cookies=Cookies, headers=Headers)
    return res.text

def recordQuestion(token, questionId, userActivityId, useTime, answerIds):
    Cookies = {"mars_token":token}
    data = {
        "questionId":questionId,
        "userActivityId":userActivityId,
        "useTime":useTime,
        "answerIds":answerIds
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/exam/v1/recordQuestion", cookies=Cookies, data=data, headers=Headers)
    return res.text

def preparePaper(token, activityId):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/exam/v1/preparePaper", data=data, cookies=Cookies, headers=Headers)
    return res.text

def startPaper(token, activityId):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/exam/v1/startPaper", cookies=Cookies, data=data, headers=Headers)
    return res.text

def getNear(token, activityId, seq):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId,
        "currentIndex":seq,
        "nearType":2
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/practice/activity/practice/v1/getNear", data=data, cookies=Cookies, headers=Headers)
    return res.text

def submitPaper(token, activityId):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId,
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/exam/v1/submitPaper", data=data, cookies=Cookies,headers=Headers)
    return res.text

def index(token):
    Cookies = {"mars_token":token}
    res = requests.post("https://mars.mycourse.cn/marsapi/api/user/v1/index", cookies=Cookies)
    return res.text
# 练习
def preparePaperPractice(token, activityId):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/practice/v1/preparePaper", data=data, cookies=Cookies, headers=Headers)
    return res.text

def startPaperPractice(token, activityId):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/practice/v1/startPaper", cookies=Cookies, data=data, headers=Headers)
    return res.text

def getNear(token, activityId, seq):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId,
        "currentIndex":seq,
        "nearType":2
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/practice/v1/getNear", data=data, cookies=Cookies, headers=Headers)
    return res.text

def submitPaperPractice(token, activityId):
    Cookies = {"mars_token":token}
    data = {
        "userActivityId":activityId,
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/practice/v1/submitPaper", data=data, cookies=Cookies,headers=Headers)
    return res.text

def recordQuestionPractice(token, questionId, userActivityId, useTime,currentIndex, answerIds):
    Cookies = {"mars_token":token}
    data = {
        "questionId":questionId,
        "userActivityId":userActivityId,
        "useTime":useTime,
        "currentIndex":currentIndex,
        "answerIds":answerIds
        }
    res = requests.post("https://mars.mycourse.cn/marsapi/api/study/activity/practice/v1/recordQuestion", cookies=Cookies, data=data, headers=Headers)
    return res.text