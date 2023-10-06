#import all packages needed for program
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageGrab
from datetime import datetime, timedelta
import time
from unicodedata import category
import textwrap
import os
from fpdf import FPDF
import glob
import math

import mysql.connector

#create a connection and cursor which allows access to the tables stored in the database hosting service (test account)
mydb = mysql.connector.connect(
  host="sql8.freemysqlhosting.net",
  user="sql8579623",
  password="xskkpLJX6R",
  database = "sql8579623"
)

mycursor = mydb.cursor(buffered= True)
mycursor2 = mydb.cursor(buffered= True)

today = datetime.today().date() 

#validates user input to check it is a numerical value only
def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

#searches the passed in records for any that are similar to user's input and updates displayed dropdown values 
def searchComparison(widget, options, records):
    #set initial dropdown options to '+ New ...'
    pairing[widget].configure(values=options)
    userEntry = (pairing[widget].get())
    userEntry = userEntry.upper()
    #display all stored records if user enters nothing
    if userEntry == '' or userEntry.isspace() == True:
        for record in records:
            options.append(record)
    #records don't need to be searched if user enters '+ New...' as different function is called
    elif userEntry != options[0].upper():
            for ch in userEntry:
                #remove any non alphabet characters from user entry
                if category(ch)[0] != 'L':
                    userEntry = userEntry.replace(ch, ' ')
            userEntry = (str(userEntry)).split()
            for record in records:
                for item in userEntry:
                    mid = len(item)//2
                    #compare by splitting each entered word longer than 3 chars into halves, and checking if present in any word in any stored record
                    if len(item)>3 and (item[:mid] in record.upper() or item[mid:] in record.upper()) and record not in options:
                        options.append(record)
    #add any records that match the conditions to the dropdown options
    pairing[widget].configure(values=options)


#intialises the records as all ingredients stored in database and calls searchComparison with them
def searchForIngredient(event):
    options = [' + New Ingredient']
    mycursor.execute("SELECT IngredientName FROM tblBaseIngredient")
    records = []
    for record in mycursor.fetchall():
        records.append(record[0])
    records.sort()
    searchComparison(event.widget, options, records)

#intialises the records as all recipes stored in database and calls searchComparison with them
def searchForRecipe(event):
    options = [' + New Recipe']
    mycursor.execute("SELECT RecipeName FROM tblBaseRecipe")
    records = []
    for record in mycursor.fetchall():
        records.append(record[0])
    records.sort()
    searchComparison(event.widget, options, records)

#intialises the records as all batch sizes stored in database for given recipe and calls searchComparison with them
def searchForBatchSize(event):
    options = [' + New Batch Size']
    records = []
    global recipeForNewBatchSize
    global includeInitial #used to flag whether the 'initial batch size' should be included in the dropdown
    mycursor.execute("SELECT BatchSizeName FROM tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipeForNewBatchSize + "' AND tblBaseRecipe.RecipeID = tblBatchSize.RecipeID")
    fetched = mycursor.fetchall()
    for i in range (len(fetched)):
        if i == 0 and includeInitial == False:
            pass
        else:
            records.append(fetched[i][0])
    records.sort()
    searchComparison(event.widget, options, records)

#intialises the records as all packaging items stored in database and calls searchComparison with them
def searchForPackaging(event):
    options = [' + New Packaging Item']
    mycursor.execute("SELECT ItemName FROM tblPackagingItems")
    records = []
    for record in mycursor.fetchall():
        records.append(record[0])
    records.sort()
    searchComparison(event.widget, options, records)

#intialises the records as all orders stored in database and calls searchComparison with them
def searchForOrder(event):
    options = []
    records = []
    mycursor.execute("SELECT OrderName FROM tblCustomerOrder")
    for record in mycursor.fetchall():
        records.append(record[0])
    records.sort()
    searchComparison(event.widget, options, records)
    
#update average weekly demand for valid ingredients 
def demandEstimation():
    #fetch all ingredients with shelf life over 28 days to update
    mycursor.execute("SELECT IngredientID, IngredientName FROM tblBaseIngredient WHERE ShelfLife >= 28")
    ingredients = mycursor.fetchall()
    for ingredient in ingredients:
        ingID = ingredient[0]
        totalQuantity = 0
        #fetch and add all quantities needed of base ingredients in orders of previous week
        mycursor.execute("SELECT Quantity FROM tblCustomerOrder, tblBaseIngredientInOrder WHERE OrderDate <= '" + str(today) + "' and IngredientID = " + str(ingID) + " and tblCustomerOrder.OrderID = tblBaseIngredientInOrder.OrderID") 
        for qty in mycursor.fetchall():
            totalQuantity += qty[0]
        #fetch and add all quantities needed of batch ingredients in orders of previous week
        mycursor.execute("SELECT Quantity FROM tblCustomerOrder, tblBatchSizeInOrder, tblIngredientInBatchSize WHERE OrderDate <= '" + str(today) + "' and IngredientID = " + str(ingID) + " and tblCustomerOrder.OrderID = tblBatchSizeInOrder.OrderID and tblBatchSizeInOrder.BatchID = tblIngredientInBatchSize.BatchID") 
        for qty in mycursor.fetchall():      
            totalQuantity += qty[0]
        #fetch current average weekly demand of ingredient from database
        mycursor.execute("SELECT AvgWeeklyDemand FROM tblBaseIngredient WHERE IngredientID = " + str(ingID))
        oldAvgQty = mycursor.fetchall()[0][0]
        #calculate new average quantity and store
        newAvgQty = (oldAvgQty + totalQuantity)/2
        mycursor.execute("UPDATE tblBaseIngredient SET AvgWeeklyDemand = " + str(newAvgQty) + " WHERE IngredientID = " + str(ingID))
        mydb.commit()


def endOfWeekReset(mondayDate):
    demandEstimation()
    #find initial shops in previous week and delete
    mycursor.execute("SELECT ShopID FROM tblInitialShoppingDates, tblCustomerOrder WHERE OrderDate < '" + str(mondayDate) + "' and tblInitialShoppingDates.OrderID = tblCustomerOrder.OrderID")
    for shop in mycursor:
        mycursor.execute("DELETE FROM tblInitialShoppingLists WHERE ShopID = " + str(shop[0]))
        mycursor.execute("DELETE FROM tblInitialShoppingDates WHERE ShopID = " + str(shop[0]))   
    #find orders completed in previous week and delete linked records
    mycursor.execute("SELECT OrderID FROM tblCustomerOrder WHERE OrderDate < '" + str(mondayDate) + "'")
    orders = mycursor.fetchall()
    for order in orders:
        orderID = order[0]
        mycursor.execute("DELETE FROM tblBatchSizeInOrder WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblBaseIngredientInOrder WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblPackagingItemInOrder WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblWorkingDateSlot WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblCustomerOrder WHERE OrderID = " + str(orderID))
    #delete reset flags records from previous week as all resets will be done
    mycursor.execute("DELETE FROM tblResetFlags WHERE Date < '" + str(mondayDate) + "'")
    #insert reset flag records for next week
    for i in range(1,8):
        date = mondayDate + timedelta(days=i)
        if i == 7:
            try:
                mycursor.execute("INSERT INTO tblResetFlags VALUES ('" + str(date) + "', 0, 0)")
            except:
                pass
        else:
            try:
                mycursor.execute("INSERT INTO tblResetFlags (Date, DailyFlag) VALUES ('" + str(date) + "', 0)")
            except:
                pass
    #mark weekly reset as done for this date
    mycursor.execute("UPDATE tblResetFlags SET ResetFlag = 1 WHERE Date = '" + str(mondayDate) + "'")
    mydb.commit()



def resetWeek():
        #put schedule back to current week first           
        global currentWeekShown
        global bottomHalfFrame
        if currentWeekShown == str(today - timedelta(days=today.weekday()))[:10]:
            generatePDF()
        else:
            currentWeekShown = str(today - timedelta(days=today.weekday()))[:10]
            global schedule
            schedule.place_forget()
            del schedule
            schedule = create_graphical_schedule(currentWeekShown, tempSlots, bottomHalfFrame)
            schedule.grid(row = 0, column = 1, padx = 40)



#takes the data from one shopping list text file and places in correct place in PDF document (called from generatePDF function)
def shoppingListToPDFList(date, pdf, lines, datexPos, dateyPos, linexPos, count):
    global extrapage
    #determine where to place the next shopping list and writes date of shop as centered title
    if dateyPos < 250:        
        pdf.text(datexPos, dateyPos, date[8]+date[9]+"/"+date[5]+date[6])
        y = dateyPos + 7
    elif extrapage == False:
        #line is too far down page and no new page yet, so add new page
        extrapage = True
        pdf.add_page()
        dateyPos = 20
        pdf.text(datexPos, dateyPos, date[8]+date[9]+"/"+date[5]+date[6])
        y = dateyPos+7
    else:
        #already an extra page which can be used
        if count == 7:
            dateyPos = dateyPos - 225
            pdf.text(datexPos, dateyPos, date[8]+date[9]+"/"+date[5]+date[6])
        else:   
            dateyPos = 20
            pdf.text(datexPos, dateyPos, date[8]+date[9]+"/"+date[5]+date[6])
        y = dateyPos+7
    #writes each ingredient of list into correct place under list date title in lines
    count = 1
    for line in lines:
        line = textwrap.wrap(line, width = 25, break_long_words = True, placeholder = '')
        for writeline in line:
            pdf.text(linexPos, y, writeline)
            y = y+7
            count = count + 1
    return count*7 #bottom y position of list
        
#runs when user clicks generate PDF button on homepage
def generatePDF():
    #take a screenshot of the current week displayed of graphical schedule    
    image = ImageGrab.grab()
    new = image.crop((1500,715,2670,1440))
    new.save(r'screenshot.png')
    image = 'screenshot.png'
    #initialise new PDF document
    pdf = FPDF(orientation = 'P')
    pdf.set_auto_page_break(True, 4)
    pdf.set_font('Arial', '', 14)
    pdf.add_page()
    global extrapage
    extrapage = False
    #insert title
    global currentWeekShown
    title = "Week Beginning " + currentWeekShown
    pdf.text(75, 30, title)
    #insert schedule screenshot into PDF at top then delete screenshot
    pdf.image(image, x=45, y=50, w=120, h=79)
    os.remove("screenshot.png")
    pdf.text(90, 146, "Shopping Lists")
    weekstart = today - timedelta(days=today.weekday())
    count = 0
    #iterate through each day in current week
    for i in range (7):
        #fetch any shopping list text files that match date
        date = weekstart + timedelta(days=i)
        date = datetime.strftime(date, "%Y-%m-%d")
        for file in os.listdir(os.getcwd()):
            if file == "ShopList" + date:
                count = count + 1
                if count == 1:
                    row = 0
                else:
                    row = ((count-1) // 3)

                fileToUse = open(file, "r")
                lines = fileToUse.readlines()
                fileToUse.close()
                
                #finds y position to place list
                if row == 0:
                    height1 = 0
                    height2 = 0
                    height3 = 0
                    #determine which column (x position) to place current list in on PDF then call function
                    if count % 3 == 1:
                        height1 = shoppingListToPDFList(date, pdf, lines, 30, 160, 20, count)
                    elif count % 3 == 2:
                        height2 = shoppingListToPDFList(date, pdf, lines, 96, 160, 83, count)
                    elif count % 3 == 0:
                        height3 = shoppingListToPDFList(date, pdf, lines, 162, 160, 146, count)
                    #finds lowest y position of this row to inform next row 
                    maxheight1 = max(height1,height2,height3)
                elif row == 1:
                    height11 = 0
                    height12 = 0
                    height13 = 0
                    if count % 3 == 1:
                        height11 = shoppingListToPDFList(date, pdf, lines, 30, 190+maxheight1, 20, count)
                    elif count % 3 == 2:
                        height12 = shoppingListToPDFList(date, pdf, lines, 96, 190+maxheight1, 83, count)
                    elif count % 3 == 0:
                        height13 = shoppingListToPDFList(date, pdf, lines, 162, 190+maxheight1, 146, count) 
                    maxheight2 = max(height1,height2,height3)
                elif row == 2:
                    if count % 3 == 1:
                        height = shoppingListToPDFList(date, pdf, lines, 30, 225+maxheight2, 20, count)
                    elif count % 3 == 2:
                        height = shoppingListToPDFList(date, pdf, lines, 96, 225+maxheight2, 83, count)
                    elif count % 3 == 0:
                        height = shoppingListToPDFList(date, pdf, lines, 162, 225+maxheight2, 146, count) 
                    
    pdf.output("Week_beginning" + str(weekstart) + ".pdf", "F")
                      
def create_graphical_schedule(weekStart, tempSlots, scheduleFrame):
        scheduleScale = 0.283333 #0.283333 is the 'pixels per minute' scale for the schedule
        frame1 = tk.Frame(scheduleFrame, width = 300, height = 15, highlightbackground="#273A36", highlightthickness=2)
        scheduleCanvas = tk.Canvas(frame1, width = 570, height = 350)
        scheduleCanvas.pack()

        #dictionary to change the starting hour of slot to position on canvas 
        timeToStartyPositionDict = {'06': 55,
                                    '07': 72,
                                    '08': 89,
                                    '09': 106,
                                    '10': 123,
                                    '11': 140,
                                    '12': 157,
                                    '13': 174,
                                    '14': 191,
                                    '15': 208,
                                    '16': 225,
                                    '17': 242,
                                    '18': 259,
                                    '19': 276,
                                    '20': 293,
                                    '21': 310,
                                    '22': 327}
        
        #dictionary to change the weekday of slot to position on canvas 
        dateToStartxPositionDict = {'Monday': 24,
                          'Tuesday': 100,
                          'Wednesday': 176,
                          'Thursday': 252,
                            'Friday': 328,
                            'Saturday': 404,
                            'Sunday': 480}

        #dictionary to change the weekday number to first letter of weekday  (for schedule headings) 
        weekdayDictionary = {1: 'M',
                     2: 'T',
                     3: 'W',
                     4: 'T',
                     5: 'F',
                     6: 'S',
                     7: 'S'}


        #create reference line for each hour between 6am and 10pm on canvas  
        y = 55
        for i in range(0,16):
            scheduleCanvas.create_line(0, y, 20, y, fill = "#273A36", width = 2)
            y = y + 17
            
        #fetch weekdays and dates for the week being displayed on schedule
        weekStart = datetime.strptime(weekStart, "%Y-%m-%d")
        weekDates=[weekStart.strftime('%d')]
        weekFullDates=[weekStart.date()]
        for i in range(1,7):
            newDate = (weekStart + timedelta(i))
            weekDates.append(newDate.strftime('%d'))
            weekFullDates.append(newDate.date())

        #place weekday letters and dates on canvas 
        x = 60
        for n in range(0,7):
            scheduleCanvas.create_text(x, 35, text=weekdayDictionary[n+1], fill="#4F2C54", font = ("Arial", 20))
            scheduleCanvas.create_text(x, 15, text=weekDates[n], fill="#D7D7D7", font = ("Arial", 15))
            x = x+76

        #create vertical lines to split each weekday on schedule
        x = 100
        for j in range(0,6):
            scheduleCanvas.create_line(x, 55, x, 330, fill = "#D7D7D7", width = 2)
            x = x + 76


        #fetch all working date slots from database 
        mycursor.execute("SELECT OrderName, Date, StartTime, EndTime FROM tblWorkingDateSlot, tblCustomerOrder WHERE tblWorkingDateSlot.OrderID = tblCustomerOrder.OrderID")
        allSlots = mycursor.fetchall()

        #format fetched PERMANENT slot start time into start hour + offset from hour - translate to positions
        for slot in allSlots:
            if slot[1] in weekFullDates:
                startTime = slot[2]
                endTime = slot[3]
                hoursAndMins = str(slot[2]).split(':')
                startTimeHour = hoursAndMins[0]
                extraMinutes = hoursAndMins[1]
                if len(startTimeHour) == 1:
                    startTimeHour = '0' + startTimeHour
                extraMinutes = int(extraMinutes)
                startyPosition = timeToStartyPositionDict[startTimeHour]+(extraMinutes*scheduleScale) 
                #find slot length (time), date and weekday - translate to positions
                slotLength = (endTime - startTime).total_seconds()/60
                date = slot[1]
                weekday = date.strftime('%A')
                startxPosition = dateToStartxPositionDict[weekday]

                #create rectangle for slot on schedule
                scheduleCanvas.create_rectangle(startxPosition, startyPosition, startxPosition+76, startyPosition+(slotLength*scheduleScale), fill="#C6D8D9", outline = "#C6D8D9")

                #find depth of slot rectangle, format and place order name of slot over rectangle 
                lineNum = int(slotLength)//60
                new_text = textwrap.wrap(slot[0], width = 7, max_lines = lineNum, break_long_words = True, placeholder = '')
                y = 15
                for line in new_text:
                    text = scheduleCanvas.create_text(startxPosition+38, startyPosition+y, text=line, fill="#273A36")
                    scheduleCanvas.tag_raise(text)
                    y = y+20

        #format fetched TEMPORARY slot start time into start hour + offset from hour - translate to positions
        if tempSlots != []:        
            for slot in tempSlots:
                if slot[1].date() in weekFullDates:
                    startTime = slot[2]
                    endTime = slot[3]
                    hoursAndMins = str(startTime.time()).split(':')
                    startTimeHour = hoursAndMins[0]
                    extraMinutes = hoursAndMins[1]
                    extraMinutes = int(extraMinutes)
                    startyPosition = timeToStartyPositionDict[startTimeHour]+(extraMinutes*scheduleScale)

                    #find slot length (time), date and weekday - translate to positions
                    slotLength = (endTime - startTime).total_seconds()/60
                    date = slot[1]
                    weekday = date.strftime('%A')
                    startxPosition = dateToStartxPositionDict[weekday]

                    #choose correct colour for prep/decor temp slots 
                    if slot[4] == 'PREP':
                        colour = '#4F2C54'
                    elif slot[4] == 'DECOR':
                        colour = '#273A36'

                    #create rectangle for slot on schedule
                    scheduleCanvas.create_rectangle(startxPosition, startyPosition, startxPosition+76, startyPosition+(slotLength*scheduleScale), fill=colour, outline = "#C6D8D9")

                    #find depth of slot rectangle, format and place order name of slot over rectangle 
                    lineNum = int(slotLength)//60
                    new_text = textwrap.wrap(slot[0], width = 7, max_lines = lineNum, break_long_words = True, placeholder = '')
                    y = 15
                    for line in new_text:
                        text = scheduleCanvas.create_text(startxPosition+38, startyPosition+y, text=line, fill='white')
                        scheduleCanvas.tag_raise(text)
                        y = y+20

        #write 'shop' on shop dates
        global previous
        #check schedule is on homepage only
        if previous[0].title() == 'Homepage Window':
            for fname in os.listdir("."):
                if fname.startswith('ShopList'):
                    #find date of list
                    date = fname[8:]
                    shopDate = datetime.strptime(date, "%Y-%m-%d").date()
                    #check if in displayed week
                    if shopDate >= weekFullDates[0] and shopDate <= weekFullDates[6]:
                        weekday = shopDate.strftime('%A')
                        #get position and write on schedule
                        startxPosition = dateToStartxPositionDict[weekday]
                        shopText = scheduleCanvas.create_text(startxPosition+40, 340, text='Shop', fill='black')
                        scheduleCanvas.tag_raise(shopText)
                        
                        
        #return the frame the schedule is placed in, so it can be placed correctly in parent window
        return frame1

#display explanation popup window for entering order dates when user clicks '?' button 
def orderDateClarifyPopup():
    global dateClarifyPopupWindow
    dateClarifyPopupWindow = tk.Toplevel()
    dateClarifyPopupWindow.grab_set()

    #format text so it fits in dimension of window and place
    clarificationText = textwrap.wrap("The order date you input MUST follow the following format to ensure processing is correct: If the order must be finished before 6pm on a certain date, please enter the PREVIOUS date. If the order can be finished after 6pm on a certain date, enter THAT date. For example, if an order is being collected at 11am on Tuesday, the order date entered should be Monday, since it must be ready by 6pm on this day before, in order to meet the early collection time the following day.", width = 50, break_long_words = False, placeholder = '')
    clarificationMessageFrame = tk.Frame(master=dateClarifyPopupWindow, background = "#C6D8D9")
    for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
    clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

    #create button to close window once user has read explanation message and place
    buttonsFrame = tk.Frame(master=dateClarifyPopupWindow)
    buttonsFrame.configure(pady=10, background = "#C6D8D9")
    confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, command = closeDateClarify, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.pack()
    buttonsFrame.place(relx=.40, rely=.80)    

    #open window and pass execution to it
    dateClarifyPopupWindow.geometry("600x500+360+140")
    dateClarifyPopupWindow.configure(background = "#C6D8D9")
    dateClarifyPopupWindow.mainloop()

#triggered when confirm button is pressed, to close popup window and pass back execution
def closeDateClarify():
    global dateClarifyPopupWindow
    dateClarifyPopupWindow.grab_release()
    dateClarifyPopupWindow.destroy()

#display explanation popup window for meaning of 'additional prep ingredients' when user clicks '?' button 
def additionalPrepClarify():
    global additionalPrepClarifyWindow
    additionalPrepClarifyWindow = tk.Toplevel()
    additionalPrepClarifyWindow.grab_set()

    #format text so it fits in dimension of window and place
    clarificationText = textwrap.wrap("Additional PREP Ingredients are ingredients used in the order, that must be purchased in time for the first PREPARATION slot linked to the order. For example, if you are adding blueberries to an (entered) batch of vanilla sponge before baking, this is an additional prep ingredient.", width = 50, break_long_words = False, placeholder = '')
    clarificationMessageFrame = tk.Frame(master=additionalPrepClarifyWindow, background = "#C6D8D9")
    for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
    clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

    #create button to close window once user has read explanation message and place
    buttonsFrame = tk.Frame(master=additionalPrepClarifyWindow)
    buttonsFrame.configure(pady=10, background = "#C6D8D9")
    confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(confirmButtonBorder, command=closeAdditionalPrepClarify, text="  Got it  ",  fg="#273A36", activeforeground='white', font=("Arial", 25), highlightbackground='#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.pack()
    buttonsFrame.place(relx=.40, rely=.80)
    
    #open window and pass execution to it
    additionalPrepClarifyWindow.geometry("600x500+360+140")
    additionalPrepClarifyWindow.configure(background = "#C6D8D9")
    additionalPrepClarifyWindow.mainloop()

#triggered when confirm button is pressed, to close popup window and pass back execution
def closeAdditionalPrepClarify():
    global additionalPrepClarifyWindow
    additionalPrepClarifyWindow.grab_release()
    additionalPrepClarifyWindow.destroy()

#display explanation popup window for meaning of 'additional decor ingredients' when user clicks '?' button 
def additionalDecorClarify():
    global additionalDecorClarifyWindow
    additionalDecorClarifyWindow = tk.Toplevel()
    additionalDecorClarifyWindow.grab_set()

    #format text so it fits in dimension of window and place
    clarificationText = textwrap.wrap("Additional DECOR Ingredients are ingredients used in the order, that must be purchased in time for the first DECORATION slot linked to the order. For example, if you are adding fondant icing to a cake (and this is not included in any entered recipe batch sizes for this order), this is an additional decor ingredient.", width = 50, break_long_words = False, placeholder = '')
    clarificationMessageFrame = tk.Frame(master=additionalDecorClarifyWindow, background = "#C6D8D9")
    for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
    clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')
    
    #create button to close window once user has read explanation message and place
    buttonsFrame = tk.Frame(master=additionalDecorClarifyWindow)
    buttonsFrame.configure(pady=10, background = "#C6D8D9")
    confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, command = closeAdditionalDecorClarify, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.pack()
    buttonsFrame.place(relx=.40, rely=.80)    

    #open window and pass execution to it
    additionalDecorClarifyWindow.geometry("600x500+360+140")
    additionalDecorClarifyWindow.configure(background = "#C6D8D9")
    additionalDecorClarifyWindow.mainloop()

#triggered when confirm button is pressed, to close popup window and pass back execution
def closeAdditionalDecorClarify():
    global additionalDecorClarifyWindow
    additionalDecorClarifyWindow.grab_release()
    additionalDecorClarifyWindow.destroy()

#display explanation popup window for meaning of 'critical ingredients' when user clicks '?' button 
def criticalClarify():
    global criticalClarifyWindow
    criticalClarifyWindow = tk.Toplevel()
    criticalClarifyWindow.grab_set()

    #format text so it fits in dimension of window and place
    clarificationText = textwrap.wrap("Critical ingredients are ones that must remain in date until 6pm on the entered order date (eg. when it is being collected/delivered, rather than just the first decoration slot. These are usually perishable ingredients that continue to deteriorate even after using them in the order, such as fresh berries. If you enter a critical ingredient in an order, there must be at least one corresponding (prep/decor) working slot within its shelf life.", width = 50, break_long_words = False, placeholder = '')
    clarificationMessageFrame = tk.Frame(master=criticalClarifyWindow, background = "#C6D8D9")
    for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
    clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

    #create button to close window once user has read explanation message and place
    buttonsFrame = tk.Frame(master=criticalClarifyWindow)
    buttonsFrame.configure(pady=10, background = "#C6D8D9")
    confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, command = closeCriticalClarify, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.pack()
    buttonsFrame.place(relx=.40, rely=.80)    

    #open window and pass execution to it#open window and pass execution to it
    criticalClarifyWindow.geometry("600x500+360+140")
    criticalClarifyWindow.configure(background = "#C6D8D9")
    criticalClarifyWindow.mainloop()

#triggered when confirm button is pressed, to close popup window and pass back execution
def closeCriticalClarify():
    global criticalClarifyWindow
    criticalClarifyWindow.grab_release()
    criticalClarifyWindow.destroy()

#display information popup window for purpose of 'add order' page when user clicks '?' button 
def infoPopup():
    global infoWindow
    infoWindow = tk.Toplevel()
    infoWindow.grab_set()
    global infoButtonMessage

    #format text so it fits in dimension of window and place
    if infoButtonMessage == 'addOrder':
        clarificationText = textwrap.wrap("This page is for entering any new orders your business recieves. Compulsory fields are Order Name, Order Date, and Working Hours. You must also have at least one base recipe, or additional ingredient. Each base recipe must have its corresponding batch size entered. Multiple recipe batches and additional ingredients can be entered, but these must be pre-recorded on the system, which can be done by pressing the 'Add New' button if not already entered. Entered details cannot be changed once entered, instead please cancel the order (or save and delete it), and then re-enter with the correct details. ", width = 60, break_long_words = False, placeholder = '')
    elif infoButtonMessage == 'homepage':
        clarificationText = textwrap.wrap("This is the homepage for the software. Each button opens a different page where details can be entered. When a dropdown list is on the page, you must press the search button first, either with the entry box blank to show all options, or with an item typed in to search for, THEN press the down arrow to see the options to select from. The schedule shows your entered working slots week by week, and the dates of any optimised shops at the bottom, and can be changed using the arrow buttons. To generate a PDF of the current week's schedule and shopping lists, press the 'Download PDF' button twice.", width = 60, break_long_words = False, placeholder = '')
    elif infoButtonMessage == 'newAccount':
        clarificationText = textwrap.wrap("Welcome to the Shopping Management Program. Once you've read this message, please enter your business name in the entry box at the top of the homepage. You are then advised to complete an initial set up process, entering some of your base ingredients, recipes, and packaging items on the pages accessed from the homepage. These can be added to/edited at any time. When you recieve customer orders, enter these on the Add Order page, using your ingredients/recipes/packaging entered. There are help buttons on each page for further explanations. You must logout after use to update the stock levels.",  width = 60, break_long_words = False, placeholder = '')
    elif infoButtonMessage == 'deleteOrder':
        clarificationText = textwrap.wrap("Search for an order and select it from the drop down to display any additional notes you entered for it. Press the delete button if you wish to delete the order from the system, and the page will indicate when this has been completed. Press cancel to close the page. All orders are automatically deleted the week after the collection date.",  width = 60, break_long_words = False, placeholder = '')
    elif infoButtonMessage == 'baseIngredients':
        clarificationText = textwrap.wrap("On this page you can enter new base ingredients, or edit ones you’ve previously entered. Search and select an ingredient to display all the fields – You must enter the shelf life and at least one purchasable quantity. Once you press confirm and the page closes, the ingredient can be used in recipes or orders.",  width = 60, break_long_words = False, placeholder = '')
    elif infoButtonMessage == 'baseRecipes':
        clarificationText = textwrap.wrap("On this page you can enter new base recipes, using any ingredients previously entered, or new ones by pressing + New Ingredient. To enter/edit multiple batch sizes of the SAME recipe, first enter all the recipe details on this page for the first batch size you are entering for this recipe. Then press confirm, and you will have the option to enter/edit the other batch sizes of THIS recipe. Once entered you cannot change which batch size is the 'initial batch size' for this recipe - You can still change the ingredients used for it, but you will need to update the ingredients for all other batch sizes of the recipe accordingly.",  width = 60, break_long_words = False, placeholder = '')
    elif infoButtonMessage == 'batchSizes':
        clarificationText = textwrap.wrap("On this page you can enter/edit batch recipes for the SAME recipe you just entered on the recipe page ONLY. To edit batch sizes for a DIFFERENT recipe, press cancel and change the recipe selected on the recipe page, then confirm. The ingredient quantities for the batch size can only be entered through the coversion method - Enter the NEW quantity for the displayed ingredient in THIS batch size and press convert, then edit any values as needed before confirming. You must have the same ingredients in each batch size of the same recipe, but in different quantities. If you need to edit the INITIAL batch size, return to the recipe page and edit it there, updating any other batch sizes accordingly afterwards.",  width = 60, break_long_words = False, placeholder = '')
    elif infoButtonMessage == 'packaging':
        clarificationText = textwrap.wrap("On this page you can enter/edit packaging items you use in orders, and their stock. Search and select a New or existing item to enter the details, then press confirm. The stock level will be monitored and more added to shopping lists when it drops below 20%.", width = 60, break_long_words = False, placeholder = '')
                                          
    clarificationMessageFrame = tk.Frame(master=infoWindow, background = "#C6D8D9")
    for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 17))
            clarificationMessage.pack()
    clarificationMessageFrame.place(relx = .5, rely = .45, anchor = 'c')

    #create button to close window once user has read explanation message and place
    buttonsFrame = tk.Frame(master=infoWindow)
    buttonsFrame.configure(pady=10, background = "#C6D8D9")
    confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, command = closeInfoPopup, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.pack()
    buttonsFrame.place(relx=.40, rely=.85)    

    #open window and pass execution to it#open window and pass execution to it
    infoWindow.geometry("600x500+360+140")
    infoWindow.configure(background = "#C6D8D9")
    infoWindow.mainloop()

#triggered when confirm button is pressed, to close popup window and pass back execution
def closeInfoPopup():
    global infoWindow
    infoWindow.grab_release()
    infoWindow.destroy()
    global newAccountPopup
    if newAccountPopup == True:
        infoButtonMessage = 'homepage'  
        homepage()


#changes the displayed week of graphical schedule to previous week
def changeShownWeekLeft():
    global schedule
    global tempSlots
    global currentWeekShown
    #sets new start of week to display
    currentWeekShown = datetime.strptime(currentWeekShown, "%Y-%m-%d")
    currentWeekShown = str(currentWeekShown - timedelta(days=7))[:10]
    #fetches where the schedule is being displayed on page currently
    parent_name = schedule.winfo_parent()
    parent = schedule._nametowidget(parent_name)
    #calls function to create new schedule display
    schedule = create_graphical_schedule(currentWeekShown, tempSlots, parent)
    #places new schedule in correct place depending on which page the user is changing it from 
    if previous[len(previous)-1].title() == 'Homepage Window':
        schedule.grid(row = 0, column = 1, padx = 40)
    else:
        schedule.place(relx = .5, rely = .25)

#changes the displayed week of graphical schedule to following week
def changeShownWeekRight():
    global schedule
    global tempSlots
    global currentWeekShown
    #sets new start of week to display
    currentWeekShown = datetime.strptime(currentWeekShown, "%Y-%m-%d")
    currentWeekShown = str(currentWeekShown + timedelta(days=7))[:10]
    #fetches where the schedule is being displayed on page currently
    parent_name = schedule.winfo_parent()
    parent = schedule._nametowidget(parent_name)
    #calls function to create new schedule display
    schedule = create_graphical_schedule(currentWeekShown, tempSlots, parent)
    #places new schedule in correct place depending on which page the user is changing it from 
    if previous[len(previous)-1].title() == 'Homepage Window':
        schedule.grid(row = 0, column = 1, padx = 40)
    else:
        schedule.place(relx = .5, rely = .25)
    

#displays the homepage of the program 
def homepage():
    #changeScreen function must be called whenever a new page is opened by user
    win = changeScreen()
    global logOutButtonBorder
    global infoButtonBorder
    global title
    #hides the title (homepage shows business name instead), and destroys all other previous widgets on page, places logout + info buttons
    for widget in welcomeWindow.winfo_children():
        if widget == title:
            title.place_forget()
        elif widget != logOutButtonBorder and widget != infoButtonBorder:
            widget.destroy()
    logOutButtonBorder.place(relx = .05, rely = .06)
    infoButtonBorder.place(relx = .85, rely = .06)
    #the homepage can't be opened as a new window so flag reset to false
    global newWindowFlag
    newWindowFlag = False

    #clears all previously opened pages and sets 'previous' array to just this window with title homepage
    global previous
    previous = [welcomeWindow]
    welcomeWindow.title('Homepage Window')
    global newAccountPopup
    global infoButtonMessage
    if newAccountPopup == True:
        infoButtonMessage == 'newAccount'
    else:
        infoButtonMessage = 'homepage'

    #creates and places business name entry widget on page  
    global businessNameEntry
    global businessName
    businessNameFrame = tk.Frame(master=welcomeWindow) 
    businessNameEntry = tk.Entry(master=businessNameFrame, width = 100, font=("Courier", 80), fg = "#4F2C54")
    businessNameEntry.configure(background = "#D8D7E8", justify = 'center', highlightbackground = "#D8D7E8")
    #fetches business name from database, inserts default text or business name into widget
    mycursor.execute("SELECT BusinessName FROM tblLoginInfo")
    businessName = mycursor.fetchall()[0][0]
    if businessName == '':
        businessNameEntry.insert(0, "Insert Business Name")
    else:
        businessNameEntry.insert(0, businessName)
    businessNameEntry.pack()
    businessNameFrame.configure(background = "#D8D7E8")
    businessNameFrame.place(relx = .5, rely = .2, anchor = 'c')

    #creates and places 'shopping management' text title on page underneath business name
    subtitleFrame = tk.Frame(master=welcomeWindow)
    subtitle = tk.Label(master=subtitleFrame, fg = "#4F2C54", background = "#D8D7E8", text="shopping management", font=("Courier", 40))
    subtitle.pack()
    subtitleFrame.place(relx = .5, rely = .3, anchor = 'c')

    #large frame for bottom half of homepage
    global bottomHalfFrame
    bottomHalfFrame = tk.Frame(master=welcomeWindow)
    
    #creates large frame for all module buttons, each module button, and places in grid formation
    mainButtonsFrame = tk.Frame(master=bottomHalfFrame)
    addOrderButton = tk.Button(master=mainButtonsFrame, width = 15, command = addOrder, activeforeground = 'white', height = 4, fg = "#273A36", highlightbackground = "#C6D8D9", text="Add Order", font=("Arial", 20))
    addOrderButton.grid(row = 0, column = 0, pady = 10, padx = 30)
    deleteOrderButton = tk.Button(master=mainButtonsFrame, width = 15, activeforeground = 'white', height = 4, fg = "#273A36", highlightbackground = "#C6D8D9", text="Delete Order", font=("Arial", 20), command = deleteOrderScreen)
    deleteOrderButton.grid(row = 0, column = 1, pady = 10, padx = 30)
    baseIngredientsButton = tk.Button(master=mainButtonsFrame,  width = 15, activeforeground = 'white', height = 4, fg = "#273A36", highlightbackground = "#C6D8D9", text="Base Ingredients", font=("Arial", 20), command = addIngredient)
    baseIngredientsButton.grid(row = 1, column = 0, pady = 10, padx = 30)
    baseRecipesButton = tk.Button(master=mainButtonsFrame,  width = 15, command = addBaseRecipe, activeforeground = 'white',  height = 4, fg = "#273A36", highlightbackground = "#C6D8D9", text="Base Recipes", font=("Arial", 20))
    baseRecipesButton.grid(row = 1, column = 1, pady = 10, padx = 30)
    packagingButton = tk.Button(master=mainButtonsFrame,  command = addEditPackaging, width = 15, activeforeground = 'white', height = 4, fg = "#273A36", highlightbackground = "#C6D8D9", text="Packaging", font=("Arial", 20))
    packagingButton.grid(row = 2, column = 0, pady = 10, padx = 30)
    PDFButton = tk.Button(master=mainButtonsFrame,  width = 15, command = resetWeek, activeforeground = 'white', height = 4, fg = "#273A36", highlightbackground = "#C6D8D9", text="Download PDF", font=("Arial", 20))
    PDFButton.grid(row = 2, column = 1, pady = 10, padx = 30)
    mainButtonsFrame.configure(background = "#D8D7E8")

    #sets week for graphical schedule to current week, temp slots to none, calls function to generate graphical schedule and places in bottom frame
    global currentWeekShown
    currentWeekShown = str(today - timedelta(days=today.weekday()))[:10]
    global schedule
    global tempSlots
    tempSlots = []
    schedule = create_graphical_schedule(currentWeekShown, tempSlots, bottomHalfFrame)
    schedule.grid(row = 0, column = 1, padx = 40)
    mainButtonsFrame.grid(row = 0, column = 0, padx = 40)
    bottomHalfFrame.configure(background = "#D8D7E8")
    bottomHalfFrame.place(relx = .1, rely =.4)

    #creates frame for arrow buttons below schedule, buttons with pre-defined images, places on page
    global arrowIconRight
    global arrowIconLeft
    arrowFrame = tk.Frame(master=welcomeWindow)
    arrowFrame.configure(background = "#D8D7E8")
    arrowButtonLeft = tk.Button(master=arrowFrame, image = arrowIconLeft, width = 30, height = 30, command = changeShownWeekLeft)
    arrowButtonLeft.grid(column = 0, row = 0)
    arrowButtonRight = tk.Button(master=arrowFrame, image = arrowIconRight, width = 30, height = 30, command = changeShownWeekRight)
    arrowButtonRight.grid(column = 1, row = 0, padx = 30)
    arrowFrame.place(relx=.68, rely=.84)

    #clears business name entry widget when user clicks on it to enter text
    def enterBusinessName(events):
        if businessNameEntry.get() == '' or businessNameEntry.get().isspace() == True or businessNameEntry.get() == 'Insert Business Name':
            businessNameEntry.delete(0, tk.END)

    #binds business name entry widget to function above when clicked
    businessNameEntry.bind("<Button-1>", enterBusinessName)

#checks the stock level of given packaging item and adds to shopping list if needed
def packagingRestock(itemID, date):
    listFlag = False
    #fetch details for given packaging item from database
    mycursor.execute("SELECT QuantityInStock, PurchaseQuantity, OnListDate, ItemName FROM tblPackagingItems WHERE PackagingID = " + str(itemID))
    record = mycursor.fetchall()[0]
    quantityInStock = record[0]
    purchaseQty = record[1]
    onListDate = record[2]
    name = record[3]
    #calculate proportion of maximum purchasable quantity in stock
    proportion = quantityInStock/purchaseQty
    #initialise flag in table as False 
    if proportion > 0.2:
        mycursor.execute("UPDATE tblPackagingItems SET OnListDate = 'None' WHERE PackagingID = " + str(itemID))
        mydb.commit()
    else:
        #add item to list if less that 20% in stock, and not already been added to a list OR earlier list date found
        shortest = timedelta(days=1000000)
        #get names of local optimised shopping files
        for file in os.listdir(os.getcwd()):
            if file.startswith("ShopList"):
                listFlag = True
                #find closest shop after current date
                shopDate = (datetime.strptime(file[8:], "%Y-%m-%d")).date()
                difference = shopDate - date
                if shopDate >= date and difference <= shortest:
                    shortest = difference
                    fileToUse = file
                    shopToUse = shopDate
        #check if date is closer than current (or if current is none)
        if onListDate == None:
            #if a suitable shop found, add item to it
            if listFlag == True:
                #open list file and write max quantity of item
                shoppingListFile = open(fileToUse, "a")
                shoppingListFile.write(name + ": " + str(purchaseQty)+ "\n")
                shoppingListFile.close()
                #set onListDate for item to true so not added more than once
                mycursor.execute("UPDATE tblPackagingItems SET OnListDate = '" + str(shopToUse) + "' WHERE PackagingID = " + str(itemID))
                mydb.commit()
            else:
                pass
                #no shops to add packaging to
        elif listFlag == True:
            if shopToUse < onListDate:
                #find shopping list that packaging item is currently included in
                oldFileName = datetime.strftime(onListDate, "%Y-%m-%d")
                oldFileName = 'ShopList' + oldFileName
                oldFile = open(oldFileName, "r")
                #store every line of this shopping list except the one with the packaging item
                lines = oldFile.readlines()
                newLines = []
                for line in lines:
                    if (line.split(': '))[0] != name:
                        newLines.append(line)
                #rewrite shopping list file with all other ingredients 
                oldFile = open(oldFileName, "w")
                for line in newLines:
                    oldFile.write(line)
                oldFile.close()            
                #open new list file and write max quantity of item
                shoppingListFile = open(fileToUse, "a")
                shoppingListFile.write(name + ": " + str(purchaseQty)+ "\n")
                shoppingListFile.close()
                #set onListDate for item to true so not added more than once
                mycursor.execute("UPDATE tblPackagingItems SET OnListDate = '" + str(shopToUse) + "' WHERE PackagingID = " + str(itemID))
                mydb.commit()
        else:
            pass #No shops to add packaging to!!
            
            
            
#runs packaging restock module for all items stored
def packagingRestockAll(date):
    mycursor.execute("SELECT PackagingID FROM tblPackagingItems")
    for ID in mycursor:
        packagingRestock(ID[0], date)

#with shopIDs
def currentStockCoverage(qtysInStock, totalIngQtyDict):
    #create list versions of stock
    qtysInStock = [list(ele) for ele in qtysInStock]
    for i in range (len(qtysInStock)):
        for dateNeeded in sorted(totalIngQtyDict.keys()):
            #get each total quantity needed  
            qtyNeeded = totalIngQtyDict[dateNeeded][0]
            if qtysInStock[i][1] >= dateNeeded and qtysInStock[i][0] > 0:
                print('the '+ str(qtysInStock[i][0]) + ' can be used for this')
                #current stock is available and expires after ingredient needed - calculate difference
                print(qtysInStock[i][0])
                totalIngQtyDict[dateNeeded][0] = totalIngQtyDict[dateNeeded][0] - qtysInStock[i][0]
                print('if it was all used we would need ' +str(totalIngQtyDict[dateNeeded][0]))
                if totalIngQtyDict[dateNeeded][0] < 0:
                    #more stock than needed - total quantity is now 0
                    totalIngQtyDict[dateNeeded][0] = 0
                    #remaining stock calculated and stored in new array
                    qtysInStock[i][0] = qtysInStock[i][0] - qtyNeeded
                    print('but we dont need it all so there is ' + str(qtysInStock[i][0]) + ' leftover')
                else:
                    #all stock used - store in new array
                    qtysInStock[i][0] = 0
                    print(' all of this stock used now')

            else:
                pass
    print('quantities needed after stock coverage are ' + str(totalIngQtyDict))
    print('leftover stock after stock coverage is ' + str(qtysInStock))
    return qtysInStock, totalIngQtyDict

#without shopIDs
def currentStockCoverage1(qtysInStock, totalIngQtyDict):
    qtysInStock = [list(ele) for ele in qtysInStock]
    for i in range (len(qtysInStock)):
        for dateNeeded in sorted(totalIngQtyDict.keys()):
            qtyNeeded = totalIngQtyDict[dateNeeded]
            if qtysInStock[i][1] >= dateNeeded and qtysInStock[i][0] > 0:
                print('the '+ str(qtysInStock[i][0]) + ' can be used for this')
                totalIngQtyDict[dateNeeded] = totalIngQtyDict[dateNeeded] - qtysInStock[i][0]
                print('if it was all used we would need ' +str(totalIngQtyDict[dateNeeded]))
                if totalIngQtyDict[dateNeeded] < 0:
                    totalIngQtyDict[dateNeeded] = 0
                    qtysInStock[i][0] = qtysInStock[i][0] - qtyNeeded
                    print('but we dont need it all so there is ' + str(qtysInStock[i][0]) + ' leftover')
                else:
                    qtysInStock[i][0] = 0

            else:
                pass
    return qtysInStock, totalIngQtyDict


#runs for each day up to current date, whenever the program is opened
def dailyStockUpdate(date):
    #delete all ingredient stock quantities that have now expired
    mycursor.execute("DELETE FROM tblItemsInStock WHERE ExpiryDate < '" + str(date) + "'")
    print('updating for ' + str(date))
    #search for any shopping lists that are being purchased today
    for file in os.listdir(os.getcwd()):
        if file == "ShopList" + str(date):
            shoppingListFile = open(file, "r")
            lines = shoppingListFile.readlines()
            #read the items and quantities needed in the shop
            for line in lines:
                wholeLine = line.split(': ')
                itemName = wholeLine[0]
                quantity = wholeLine[1]
                print(wholeLine)
                try:
                    #item on list is ingredient
                    mycursor.execute("SELECT IngredientID, ShelfLife FROM tblBaseIngredient WHERE IngredientName = '" + itemName + "'")
                    record = mycursor.fetchall()[0]
                    ingID = record[0]
                    shelfLife = record[1]
                    #calculate expiry date for new stock item and add to database
                    expiryDate = date + timedelta(days=shelfLife)
                    mycursor.execute("INSERT INTO tblItemsInStock VALUES (" + str(ingID) + ", " + str(quantity) + ", '" + str(expiryDate) + "')")
                    mydb.commit()
                except:
                    #item on list is packaging
                    print(itemName)
                    mycursor.execute("SELECT PackagingID, QuantityInStock FROM tblPackagingItems WHERE ItemName = '" + itemName + "'")
                    record = mycursor.fetchall()[0]
                    #calculate new larger quantity of item and store in database 
                    itemID = record[0]
                    oldQty = record[1]
                    newQty = oldQty + float(quantity)
                    mycursor.execute("UPDATE tblPackagingItems SET QuantityInStock = " + str(newQty) + " WHERE PackagingID = " + str(itemID))
                    mydb.commit()
    #find all ingredients in orders with current date as date required
    allIngs = {}
    #find all additional ingredients
    mycursor.execute("SELECT tblBaseIngredient.IngredientID, Quantity, EndDateRequired FROM tblBaseIngredientInOrder, tblBaseIngredient WHERE tblBaseIngredient.IngredientID = tblBaseIngredientInOrder.IngredientID and DateRequired = '" + str(date) + "'")
    for ingredient in mycursor:
        ingID = ingredient[0]
        quantity = ingredient[1]
        endDate = ingredient[2]
        try:
            #add the end date and quantity to dictionary for this ingredient if other instances already
            values = allIngs[ingID]
            values.extend((endDate, quantity))
            allIngs[ingID] = values
        except:
            #add the end date and quantity to dictionary for this ingredient if new
            allIngs[ingID] = [(endDate, quantity)]
    #find all ingredients within batches
    mycursor.execute("SELECT tblIngredientInBatchSize.IngredientID, Quantity, EndDateRequired FROM tblBatchSizeInOrder, tblIngredientInBatchSize WHERE tblIngredientInBatchSize.BatchID = tblBatchSizeInOrder.BatchID and DateRequired = '" + str(date) + "'")
    for ingredient in mycursor:
        ingID = ingredient[0]
        quantity = ingredient[1]
        endDate = ingredient[2]
        try:
            #add the end date and quantity to dictionary for this ingredient if other instances already
            values = allIngs[ingID]
            values.extend((endDate, quantity))
            allIngs[ingID] = values
        except:
            #add the end date and quantity to dictionary for this ingredient if new
            allIngs[ingID] = [(endDate, quantity)]
    #calculate stock usage for each ingredient found above 
    for ingID in allIngs:
        print(ingID)
        #create dictionary of all instances for this ingredient
        totalIngQtyDict = {}
        for instance in allIngs[ingID]:
            endDate = instance[0]
            quantity = instance[1]
            try:
                #if instances with same expiry date exist
                totalIngQtyDict[endDate] = totalIngQtyDict[endDate] + quantity
            except:
                #if no instances with same expiry date exist
                totalIngQtyDict[endDate] = quantity
        #fetch quantities in stock for this ingredient
        mycursor.execute("SELECT tblItemsInStock.Quantity, ExpiryDate from tblItemsInStock WHERE tblItemsInStock.IngredientID = " + str(ingID) + " ORDER BY ExpiryDate")
        qtysInStock = mycursor.fetchall()
        print(qtysInStock)
        #calculate how this current stock can cover the ingredient quantity instances needed
        leftovers, needed = currentStockCoverage1(qtysInStock, totalIngQtyDict)
        for qty in needed:
            print('qty needed should be 0: '+ str(needed[qty]))
        #find any stock quantities that have been completely used up to delete from database
        for leftover in leftovers:
            expiry = leftover[1]
            if leftover[0] == 0:
                #there should be only one record of each ingredient in stock with a given expiry date so delete this one
                mycursor.execute("DELETE FROM tblItemsInStock WHERE IngredientID = " + str(ingID) + " and ExpiryDate = '" + str(expiry) + "' LIMIT 1")
                mydb.commit()
            else:
                #there should be only one record of each ingredient in stock with a given expiry date so update this one
                mycursor.execute("UPDATE tblItemsInStock SET Quantity = " + str(leftover[0]) + " WHERE IngredientID = " + str(ingID) + " and ExpiryDate = '" + str(expiry) + "'")
                mydb.commit()
    #find all orders being completed today
    mycursor.execute("SELECT OrderID FROM tblCustomerOrder WHERE OrderDate = '" + str(date) + "'")
    for order in mycursor:
        orderID = order[0]
        #find any packaging needed for these orders
        mycursor.execute("SELECT PackagingID, Quantity FROM tblPackagingItemInOrder WHERE OrderID = " + str(orderID))
        for record in mycursor:
            packagingID = record[0]
            quantity = record[1]
            #fetch current quantity in stock of this packaging item
            mycursor.execute("SELECT QuantityInStock FROM tblPackagingItems WHERE PackagingID = " + str(packagingID))
            #recalculate quantity in stock by subtracting amount used in order and store in database
            oldQty = mycursor.fetchall()[0][0]
            newQty = oldQty - quantity
            mycursor.execute("UPDATE tblPackagingItems SET QuantityInStock = " + str(newQty) + " WHERE PackagingID = " + str(packagingID))
            mydb.commit()
            packagingRestock(packagingID, today)
    #set daily flag = True as module done
    mycursor.execute("UPDATE tblResetFlags SET DailyFlag = True WHERE Date = '" + str(date) + "'")
    mydb.commit()
    #check if end of week reset needed (mondays)
    mycursor.execute("SELECT ResetFlag FROM tblResetFlags WHERE Date = '" + str(date) + "'")
    resetFlag = mycursor.fetchall()[0][0]
    if resetFlag == False:
        endOfWeekReset(date)
       

#displays registration and login page 
def registration_login():
    #destroys all widgets on page except logout and info buttons, and page title
    for widget in welcomeWindow.winfo_children():
        if widget != logOutButtonBorder and  widget != title and  widget != infoButtonBorder:
            widget.destroy()

    #clears all previously opened pages and sets 'previous' array to just this window with title registration/login
    global previous
    previous = [welcomeWindow]
    welcomeWindow.title('Registration Login Window')
    #the reg/login page can't be opened as a new window so flag reset to false
    global newWindowFlag
    newWindowFlag = False

    if newAccountPopup == True:
        dailyStockUpdate(today)
        
    #manages whether the screen displays widgets for registration or login when button changed
    def loginClicked():
        #swaps highlight colour of reg/login buttons
        loginButton.configure(highlightbackground='#D7D7D7')
        registerButton.configure(highlightbackground='#C6D8D9')
        #removes extra widgets from registration fields
        confirmPasswordLabel.grid_remove()
        confirmPasswordEntry.grid_remove()
        confirmEmailLabel.grid_remove()
        confirmEmailEntry.grid_remove()
        notMatchingAlert.configure(text = '')
        #changes page state to login
        global state
        state = 'login'

    def registerClicked():
        #swaps highlight colour of reg/login buttons
        registerButton.configure(highlightbackground='#D7D7D7')
        loginButton.configure(highlightbackground='#C6D8D9')
        #displays extra widgets for registration fields
        emailLabel.grid(row=0)
        confirmEmailLabel.grid(row=1)
        passwordLabel.grid(row=2)
        confirmPasswordLabel.grid(row=3)
        emailEntry.grid(row=0, column=1, pady = 20)
        confirmEmailEntry.grid(row=1, column=1, pady = 20)
        passwordEntry.grid(row=2, column=1, pady = 20)
        confirmPasswordEntry.grid(row=3, column=1, pady = 20)
        notMatchingAlert.configure(text = '')
        #changes page state to registration
        global state
        state = 'register'

    #triggered when confirm button pressed to validate entries and complete registration/login process 
    def entry():
        #fetches user entries from page widgets
        currentEmail = (emailEntry.get()).lower()
        currentPassword = (passwordEntry.get()).lower()
        currentEmail2 = (confirmEmailEntry.get()).lower()
        currentPassword2 = (confirmPasswordEntry.get()).lower()
        #clears widget entries
        emailEntry.delete(0, tk.END)
        passwordEntry.delete(0, tk.END)
        confirmEmailEntry.delete(0, tk.END)
        confirmPasswordEntry.delete(0, tk.END)

        #validates entries for registration
        if state == 'register' and currentEmail2 != currentEmail and  currentPassword2 != currentPassword:
            notMatchingAlert.configure(text = 'Emails and passwords not matching')
        elif state == 'register' and currentEmail2 != currentEmail:
            notMatchingAlert.configure(text = 'Emails not matching')
        elif state == 'register' and currentPassword2 != currentPassword:
            notMatchingAlert.configure(text = 'Passwords not matching')
        elif state == 'register' and (currentPassword2 == '' or currentPassword == '' or currentEmail2 == '' or currentEmail == ''):
            notMatchingAlert.configure(text = 'Fields left blank')
        #validates entries for login
        elif state == 'login' and currentPassword == '' or currentEmail == '':
            notMatchingAlert.configure(text = 'Fields left blank')
        else:
            #FORMATS are valid
            notMatchingAlert.configure(text = '')
            if state == 'register':
                #write entered details to database
                mycursor.execute("DELETE FROM tblLoginInfo")
                mycursor.execute("DELETE FROM tblResetFlags")
                mycursor.execute("INSERT INTO tblLoginInfo VALUES ('" + currentEmail + "', '" + currentPassword + "', ' ')")
                notMatchingAlert.configure(text = 'Account created - Please login.')
            elif state == 'login':
                #check entered details against database
                mycursor.execute("SELECT Email, Password FROM tblLoginInfo")
                account = mycursor.fetchall()[0]
                storedEmail = account[0]
                storedPassword = account[1]
                if storedEmail != currentEmail and  storedPassword != currentPassword:
                    notMatchingAlert.configure(text = 'Email and password not correct')
                elif storedEmail != currentEmail:
                    notMatchingAlert.configure(text = 'Email not correct')
                elif storedPassword != currentPassword:
                    notMatchingAlert.configure(text = 'Password not correct')
                else:
                    #all details validated and verified - run weekly update checks then display homepage
                    try:
                        #get last stored date of login
                        mycursor.execute("SELECT Date FROM tblResetFlags ORDER BY Date DESC LIMIT 1")
                        lastDate = mycursor.fetchall()[0][0]
                        date = lastDate + timedelta(days=1)
                    except:
                        #no dates previously logged in - add today
                        if today.weekday() == 0:
                            mycursor.execute("INSERT INTO tblResetFlags VALUES ('" + str(today) + "', 0, 0)")
                        else:
                            mycursor.execute("INSERT INTO tblResetFlags (Date, DailyFlag) VALUES ('" + str(today) + "', 0)")
                        mydb.commit()
                        global newAccountPopup
                        newAccountPopup = True
                        global infoButtonMessage
                        infoButtonMessage = 'newAccount'
                        infoPopup()
                    #add records to ResetFlags table for any missing dates between last stored date and current date, dailyFlag = False, resetFlag = NULL or False for Mondays
                    try:
                        #if a previous date was found, increment up to today and add to DB
                        while date <= today:
                            if date.weekday() == 0:
                                mycursor.execute("INSERT INTO tblResetFlags VALUES ('" + str(date) + "', 0, 0)")
                            else:
                                mycursor.execute("INSERT INTO tblResetFlags (Date, DailyFlag) VALUES ('" + str(date) + "', 0)")
                            date = date + timedelta(days=1)
                        mydb.commit()
                    except:
                        #no other dates needed to add
                        pass
                    #run daily stock update for all non updated dates up to current date
                    mycursor.execute("SELECT Date FROM tblResetFlags WHERE Date <= '" + str(today) + "' and DailyFlag = False")
                    dates = mycursor.fetchall()
                    for date in dates:
                        dailyStockUpdate(date[0])
                    homepage()
            
    #intialise state to login (not registration)
    global state
    state = 'login'
    #set title to generic pre-login title
    title.configure(text = 'Shopping Management')
    title.place(relx =.5, rely = .1, anchor = 'c')

    #create and place login or registration option buttons 
    ButtonFrame = tk.Frame(master=welcomeWindow, background = "#D8D7E8")
    loginButton = tk.Button(master=ButtonFrame, text="Login", activeforeground='blue', highlightbackground='#D7D7D7', font = ("Arial", 35), command = loginClicked)
    loginButton.pack(pady = 10)
    registerButton = tk.Button(master=ButtonFrame, text="Register", activeforeground='blue', highlightbackground='#C6D8D9', font = ("Arial", 35), command = registerClicked)
    registerButton.pack()
    ButtonFrame.pack(pady=(200,30))

    #frame for all entry widgets
    entryFrame = tk.Frame(master=welcomeWindow, background = "#D8D7E8")

    #create all email and password labels and entries, place only login fields in grid
    emailLabel = tk.Label(master=entryFrame, text="Email:", fg = "#4F2C54", background = "#D8D7E8", font = ("Arial", 20))
    emailLabel.grid(row=0)
    emailEntry = tk.Entry(master=entryFrame, width = 100)
    emailEntry.grid(row=0, column=1, pady = 20)
    
    confirmEmailLabel = tk.Label(master=entryFrame, text="Confirm Email:", fg = "#4F2C54", background = "#D8D7E8", font = ("Arial", 20))
    confirmEmailEntry = tk.Entry(master=entryFrame, width = 100)
    
    passwordLabel = tk.Label(master=entryFrame, text="Password:", fg = "#4F2C54", background = "#D8D7E8", font = ("Arial", 20))
    passwordLabel.grid(row=2)
    passwordEntry = tk.Entry(master=entryFrame, width = 100)
    passwordEntry.grid(row=2, column=1, pady = 20)
    
    confirmPasswordEntry = tk.Entry(master=entryFrame, width = 100)
    confirmPasswordLabel = tk.Label(master=entryFrame, text="Confirm Password:", fg = "#4F2C54", background = "#D8D7E8", font = ("Arial", 20))

    entryFrame.pack()

    #create and display confirmation button at bottom of page
    confirmFrame = tk.Frame(master=welcomeWindow)
    confirmFrame.configure(pady=50, background = "#D8D7E8")
    confirmButton = tk.Button(master=confirmFrame, text="Confirm", activeforeground='blue', font = ("Arial", 35), highlightbackground = '#C6D8D9', command = entry)
    confirmButton.pack()
    confirmFrame.pack()

    #create and display alert message frame, with no text in yet
    message = ''
    notMatchingAlertFrame = tk.Frame(master=welcomeWindow)
    notMatchingAlert = tk.Label(master=notMatchingAlertFrame, fg = "#4F2C54", text=message, font=("Arial", 30), background = "#D8D7E8")
    notMatchingAlert.pack()
    notMatchingAlertFrame.pack(pady=30)

#deleted a selected order
def deleteOrder():
    #fetch order name to delete
    global orderNameCombo
    orderName = orderNameCombo.get()
    #find ID of this orders
    mycursor.execute("SELECT OrderID FROM tblCustomerOrder WHERE OrderName = '" + orderName + "'")
    try:
        orderID = mycursor.fetchall()[0][0]
        #find shops linked to order and delete
        mycursor.execute("SELECT ShopID FROM tblInitialShoppingDates WHERE OrderID = '" + str(orderID) + "'")
        shops = mycursor.fetchall()
        for shop in shops:
            mycursor.execute("DELETE FROM tblInitialShoppingLists WHERE ShopID = " + str(shop[0]))
            mycursor.execute("DELETE FROM tblInitialShoppingDates WHERE ShopID = " + str(shop[0]))
        mydb.commit()
        #delete correct records in all other tables linked to order
        mycursor.execute("DELETE FROM tblBatchSizeInOrder WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblBaseIngredientInOrder WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblPackagingItemInOrder WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblWorkingDateSlot WHERE OrderID = " + str(orderID))
        mycursor.execute("DELETE FROM tblCustomerOrder WHERE OrderID = " + str(orderID))
        mydb.commit()
        #display complete message to user
        global notMatchingAlert
        notMatchingAlert.configure(text = 'Order deleted - Cannot undo')
        shoppingOptimisation()
    except:
        notMatchingAlert.configure(text = 'Order not found')
        
def clearMessage(event):
    global notMatchingAlert
    notMatchingAlert.configure(text = '')
    global orderNameCombo
    global additionalNotes
    global row2Frame
    orderName = orderNameCombo.get()
    mycursor.execute("SELECT AdditionalNotes FROM tblCustomerOrder WHERE OrderName = '" + str(orderName) + "'")
    notes = mycursor.fetchall()[0][0]
    additionalNotes.configure(state="normal")
    additionalNotes.delete(0, tk.END)
    additionalNotes.insert(0, notes)
    additionalNotes.configure(state="disabled")
    
def deleteOrderScreen():
    #call change screen module once page opened 
    win = changeScreen()
    global includeOrderInitial
    includeOrderInitial = False
    #destroy all widgets on page except login/info buttons and title
    for widget in welcomeWindow.winfo_children():
        global logOutButtonBorder
        global infoButtonBorder
        global title
        if widget != logOutButtonBorder and  widget != title and  widget != infoButtonBorder:
            widget.destroy()
        #set title widget to correct text
        title.configure(text = 'Delete Order')
        title.place(relx =.5, rely = .1, anchor = 'c')

    #name window and add as previous window 
    global previous
    previous = [welcomeWindow]
    welcomeWindow.title("Delete Order Window")
    global infoButtonMessage
    infoButtonMessage = 'deleteOrder'

    global orderNameCombo
    row1Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    orderNameLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="Order Name", font=("Arial", 20))
    orderNameLabel.grid(row = 0, column = 0)
    orderNameCombo = ttk.Combobox(row1Frame, textvariable=tk.StringVar(), width = 100, values=[], style = "TCombobox")
    orderNameCombo.grid(row=0, column = 1, padx = (39,0))
    searchButton = tk.Button(row1Frame, text='Search')
    searchButton.grid(row=0, column = 2, padx = (3,0))
    searchButton.bind('<Button>', searchForOrder)
    orderNameCombo.bind('<<ComboboxSelected>>', clearMessage)
    pairing[searchButton] = orderNameCombo
    row1Frame.place(relx = .1, rely = .25)

    global additionalNotes
    global row2Frame
    row2Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    orderNameLabel = tk.Label(master=row2Frame, fg = "#4F2C54", background = "#D8D7E8", text="Notes", font=("Arial", 20))
    orderNameLabel.grid(row = 0, column = 0)
    additionalNotes = tk.Entry(row2Frame, width = 100)
    additionalNotes.grid(row=0, column = 1, padx = (39,0))
    row2Frame.place(relx = .15, rely = .4)

    confirmFrame = tk.Frame(master=welcomeWindow, bg = "#D8D7E8")
    cancelButtonBorder = tk.Frame(confirmFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    cancelButton = tk.Button(master=cancelButtonBorder, text="Cancel", activeforeground='white', fg = "#273A36", command = homepage, font = ("Arial", 25), highlightbackground = '#C6D8D9')
    cancelButton.pack()
    cancelButtonBorder.grid(column=1, row = 0, padx = 20)
    deleteButtonBorder = tk.Frame(confirmFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    deleteButton = tk.Button(master=deleteButtonBorder, text="Delete Order", activeforeground='white', fg = "#273A36", command = deleteOrder, font = ("Arial", 25), highlightbackground = '#C6D8D9')
    deleteButton.pack()
    deleteButtonBorder.grid(column=0, row = 0, padx = 20)
    confirmFrame.place(relx = .5, rely = .6, anchor = 'c')

    global notMatchingAlert
    notMatchingAlertFrame = tk.Frame(master=welcomeWindow)
    notMatchingAlert = tk.Label(master=notMatchingAlertFrame, fg = "#4F2C54", text='', font=("Arial", 30), background = "#D8D7E8")
    notMatchingAlert.pack()
    notMatchingAlertFrame.place(relx = .5, rely = .5, anchor = 'c')


#displays base recipe entry page 
def addBaseRecipe():

    #allows user to fully logout if this page has been opened in a new window 
    def logOutFromNewWindow():
        global newWindowFlag
        newWindowFlag = False
        win = changeScreen()
        window3.destroy()
        registration_login()

    def closeModule():
        global window3
        global previous
        global newWindowFlag
        if newWindowFlag == True:
            #close new window and return execution
            window3.grab_release()
            window3.destroy()
            previous.pop()
        else:
            #if on original page, this recipe page can only have been called from homepage so return to homepage
            newWindowFlag == False
            homepage()

    #call change screen module once page opened 
    win = changeScreen()
    global newWindowFlag
    #determine whether page needs opening in a new window or existing one
    if newWindowFlag == False:
        global window3
        window3 = welcomeWindow
        #destroy all widgets on page except login/info buttons and title
        for widget in window3.winfo_children():
            global logOutButtonBorder
            global infoButtonBorder
            global title
            if widget != logOutButtonBorder and  widget != title and  widget != infoButtonBorder:
                widget.destroy()
            #set title widget to correct text
            title.configure(text = 'Add/Edit Base Recipe')
            title.place(relx =.5, rely = .1, anchor = 'c')
    else:
        #create new window and recreate logout/info buttons and title
        window3 = tk.Tk()
        window3.grab_set()
        newlogOutButtonBorder = tk.Frame(master=window3, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        newlogOutButton = tk.Button(master=newlogOutButtonBorder, command = logOutFromNewWindow, justify = 'center', text = '-->', width = 7, height = 4)
        newlogOutButton.pack()
        newlogOutButtonBorder.place(relx = .05, rely = .06)
        newtitle = tk.Label(master=window3, fg = "#4F2C54", text = 'Add/Edit Base Recipe', bg = "#D8D7E8", font=("Courier", 80))
        newtitle.place(relx =.5, rely = .1, anchor = 'c')
        newinfoButtonBorder = tk.Frame(master=window3, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        newinfoButton = tk.Button(master=newinfoButtonBorder, text = "?", width = 2, font = ("Arial", 50),highlightbackground = '#C6D8D9')
        newinfoButton.pack()
        newinfoButtonBorder.place(relx = .85, rely = .06)


    #name window and add as previous window 
    window3.title("Recipe Window")
    global previous
    if newWindowFlag == True:
        previous.append(window3)
    else:
        previous = [window3]
    global infoButtonMessage
    infoButtonMessage = 'baseRecipes'

    #triggered whenever a new widget is clicked
    def enterValue(event):
            global ingredientRows
            if event.widget.winfo_class() == 'Entry':
                if event.widget.get() == ' Qty':
                    #deletes format placeholder in clicked widget so user can enter text
                    event.widget.delete(0, tk.END)
                    event.widget.configure(fg = 'black')
                    for row in ingredientRows:
                        for item in row.children.items():
                                #re-enter format placeholder in any other empty entry widgets 
                                if '!entry' in item[0] and item[1].get() == '' and item[1] != event.widget:
                                    item[1].configure(fg = '#D7D7D7')
                                    item[1].insert(0, ' Qty')
            else:
                #when button clicked (not entry)
                for row in ingredientRows:
                        for item in row.children.items():
                                #re-enter format placeholder in any other empty entry widgets 
                                try:
                                    if item[1].get() == '':
                                        item[1].configure(fg = '#D7D7D7')
                                        item[1].insert(0, ' Qty')
                                except:
                                    pass

    #display explanation popup window for entering purchasable quantities when user clicks '?' button 
    def initialClarifyPopup():
        global initialClarifyPopupWindow
        initialClarifyPopupWindow = tk.Toplevel()
        initialClarifyPopupWindow.grab_set()

        #format text so it fits in dimension of window and place
        clarificationText = textwrap.wrap("The initial batch size is the first batch size you are entering for this recipe, which will act as the reference for any other batch sizes of THIS recipe. Once entered you cannot change which batch size is the 'initial batch size' for this recipe - You can still change the ingredients used for it, but you will need to update the ingredients for all other batch sizes of the recipe accordingly.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=initialClarifyPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
                clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
                clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=initialClarifyPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeInitialClarify, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        initialClarifyPopupWindow.geometry("600x500+360+140")
        initialClarifyPopupWindow.configure(background = "#C6D8D9")
        initialClarifyPopupWindow.mainloop()

    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeInitialClarify():
        global initialClarifyPopupWindow
        initialClarifyPopupWindow.grab_release()
        initialClarifyPopupWindow.destroy()

    #validates all entered fields and updates database
    def validate():
        invalidFields = []
        #checking recipe field
        global recipeNameCombo
        recipeEntered = recipeNameCombo.get()
        global initialBatchSizeEntry
        mycursor.execute("SELECT RecipeName FROM tblBaseRecipe")
        flag = False
        if recipeEntered == ' + New Recipe':
            flag = True
        else:
            for record in mycursor:
                if recipeEntered == record[0]:
                    flag = True

        #invalid if recipe entered by user is not stored in database or '+ New...'
        if flag == False:
            invalidFields.append('Recipe Name')
        
        #checking new recipe field when '+ New...' chosen
        global recipeForNewBatchSize
        if newRecipeNameEntry.winfo_ismapped() == True:
            recipeForNewBatchSize = newRecipeNameEntry.get()
            #invalid if new recipe name left blank
            if (newRecipeNameEntry.get().isspace() == True) or (newRecipeNameEntry.get() == ''):
                invalidFields.append('New Recipe Name')
        else:
            recipeForNewBatchSize = recipeEntered
            
        #checking initial batch size field - invalid if batch size left blank
        if (initialBatchSizeEntry.get().isspace() == True) or (initialBatchSizeEntry.get() == ''):
            invalidFields.append('Initial Batch Size')

        #checking ingredient fields
        global ingredientRows
        noIngredientFlag = True
        for row in ingredientRows:
                for i in range (len(row.winfo_children())):
                        if row.winfo_children()[i].winfo_class() == 'TCombobox':
                            #fetch each entered ingredient and quantity pair from page
                            ingredientEntered = row.winfo_children()[i].get()
                            quantityEntered = row.winfo_children()[i+2].get()                                
                            if ingredientEntered == '' or ingredientEntered.isspace() == True:
                                if quantityEntered == '' or quantityEntered.isspace() == True or quantityEntered == ' Qty':
                                    pass
                                else:
                                    #invalid if ingredient name left blank but quantity is not
                                    invalidFields.append('Ingredient for '+ str(quantityEntered))
                            else:
                                floatFlag = isfloat(quantityEntered)
                                if floatFlag == False:
                                    invalidFields.append('Quantity for ' + ingredientEntered)
                                else:
                                    #valid pair
                                    noIngredientFlag = False

                            if quantityEntered == '' or quantityEntered.isspace() == True or quantityEntered == ' Qty':
                                if ingredientEntered == '' or ingredientEntered.isspace() == True:
                                    pass
                                else:
                                    #invalid if quantity left blank but ingredient name is not
                                    invalidFields.append('Quantity for '+ ingredientEntered)
                            else:
                                #valid pair
                                noIngredientFlag = False

        #invalid as at least one ingredient must be entered per recipe
        if noIngredientFlag == True:
            invalidFields.append('At least one ingredient')
            
        #initialise flag
        global existingRecipeFlag
        existingRecipeFlag = False

        #display error message popup if any invalid fields were identified  
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            validationPopup(invalidFields)
        else:
            #check new recipe name chosen is not already taken (unless the record is just from entering a different batch of this recipe already)
            if recipeEntered == ' + New Recipe':
                mycursor.execute("SELECT RecipeName FROM tblBaseRecipe")
                allrecipes = mycursor.fetchall()
                recipeEntered = newRecipeNameEntry.get()
                global batchAdded
                for recipe in allrecipes:
                    if recipeEntered == recipe[0] and batchAdded == False:
                        existingRecipeFlag = True
                        #display error message
                        validationPopup('')
                if existingRecipeFlag == False and batchAdded == False:
                    #all fields valid and data not saved yet - save new recipe and corresponding initial batch size to database
                    #add recipe record
                    mycursor.execute("INSERT INTO tblBaseRecipe (RecipeName) VALUES ('" + recipeEntered + "')")
                    mycursor.execute("SELECT RecipeID FROM tblBaseRecipe WHERE RecipeName = '"+ recipeEntered + "'")
                    recipeID = mycursor.fetchall()[0][0]
                    #add intial batch size record
                    mycursor.execute("INSERT INTO tblBatchSize (RecipeID, BatchSizeName) VALUES (" + str(recipeID) + ", '" + initialBatchSizeEntry.get() +"')")
                    mycursor.execute("SELECT BatchID FROM tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipeEntered + "' AND tblBaseRecipe.RecipeID = tblBatchSize.RecipeID and BatchSizeName = '" + initialBatchSizeEntry.get() + "'")
                    mydb.commit()
                    batchID = mycursor.fetchall()[0][0]
                    #add records for ingredients and quantities in initial batch size
                    for row in ingredientRows:
                        for i in range (len(row.winfo_children())):
                            if row.winfo_children()[i].winfo_class() == 'TCombobox' and row.winfo_children()[i].get().isspace() == False and row.winfo_children()[i].get() != '':
                                #find ingredientID
                                ingredientName = row.winfo_children()[i].get()
                                mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '" + ingredientName + "'")
                                ingredientID = mycursor.fetchall()[0][0]
                            elif row.winfo_children()[i].winfo_class() == 'Entry' and row.winfo_children()[i].get().isspace() == False and row.winfo_children()[i].get() != '' and row.winfo_children()[i].get() != ' Qty':
                                #add to database with corresponding quantity
                                ingredientQuantity = row.winfo_children()[i].get()
                                mycursor.execute("INSERT INTO tblIngredientInBatchSize VALUES (" + str(batchID) + ", " + str(ingredientID) + ", " + str(ingredientQuantity) + ")")
                                mydb.commit()
                    #ask user if they want to enter another batch size for this order (see function)
                    batchSizePopup()
                elif existingRecipeFlag == False:
                    #data already saved from adding another batch so immediately just ask user if they want to enter another batch size for this order (see function)
                    batchSizePopup()
            else:
                #all fields valid - update stored recipe and corresponding initial batch size in database
                mycursor.execute("SELECT BatchID FROM tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipeEntered + "' AND tblBaseRecipe.RecipeID = tblBatchSize.RecipeID and BatchSizeName = '" + initialBatchSizeEntry.get() + "'")
                batchID = mycursor.fetchall()[0][0]
                #update ingredients using this BatchID by deleting and rewriting (does not break referential integrity)
                mycursor.execute("DELETE FROM tblIngredientInBatchSize WHERE BatchID = " + str(batchID))
                for row in ingredientRows:
                        for i in range (len(row.winfo_children())):
                            if row.winfo_children()[i].winfo_class() == 'TCombobox' and row.winfo_children()[i].get().isspace() == False and row.winfo_children()[i].get() != '':
                                #find ingredientID
                                ingredientName = row.winfo_children()[i].get()
                                mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '" + ingredientName + "'")
                                ingredientID = mycursor.fetchall()[0][0]
                            elif row.winfo_children()[i].winfo_class() == 'Entry' and row.winfo_children()[i].get().isspace() == False and row.winfo_children()[i].get() != '' and row.winfo_children()[i].get() != ' Qty':
                                #find ingredientID
                                ingredientQuantity = row.winfo_children()[i].get()
                                mycursor.execute("INSERT INTO tblIngredientInBatchSize VALUES (" + str(batchID) + ", " + str(ingredientID) + ", " + str(ingredientQuantity) + ")")
                mydb.commit()
                #re-calculate shopping dates for any orders including this batch
                mycursor.execute("SELECT OrderID FROM tblBatchSizeInOrder WHERE BatchID = " + str(batchID))
                orders = mycursor.fetchall()
                for order in orders:
                    initialShopDateScheduling(order[0])
                shoppingOptimisation()
                #ask user if they want to enter another batch size for this order (see function)
                batchSizePopup()

    #creates and displays popup window to alert user of any invalid field entries on page            
    def validationPopup(invalidFields):
        global validationPopupWindow
        validationPopupWindow = tk.Toplevel()
        global window3
        window3.grab_release()
        validationPopupWindow.grab_set()

        #format text so it fits in dimension of window and place
        global existingRecipeFlag
        if existingRecipeFlag != True:
            clarificationText = textwrap.wrap("Please enter a valid " + invalidFields, width = 50, break_long_words = False, placeholder = '')
        else:
            clarificationText = textwrap.wrap("Recipe name is already taken. Please enter a different name.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=validationPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=validationPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeValidationPopup, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        validationPopupWindow.geometry("600x500+360+140")
        validationPopupWindow.configure(background = "#C6D8D9")
        validationPopupWindow.mainloop()

    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeValidationPopup():
        global validationPopupWindow
        validationPopupWindow.grab_release()
        validationPopupWindow.destroy()

    #checks if the user wants the recipe to contain a new ingredient so the new ingredient module will need to run
    def checkForModuleChange(event):
        global ingredientRows
        for row in ingredientRows:
                for i in range (len(row.winfo_children())):
                    widget = row.winfo_children()[i]
                    #check all ingredient combobox values on page only 
                    if widget.winfo_class() == 'TCombobox':
                        if widget.get() == ' + New Ingredient':
                            #add ingredient page will need to open in a new window on top of recipe window so set flag
                            global newWindowFlag
                            newWindowFlag = True
                            global newIngredientFlag
                            newIngredientFlag = True
                            addIngredient()

    #triggered by the '+' button to add another row of entry fields for ingredients in recipe 
    def addIngredientRow():
        global ingredientRows
        global addIngredientRowButton
        #use number of existing rows to inform where to place new row on page
        if len(ingredientRows) == 2:
            row = newIngredientRow()
            row.place(relx = .08, rely = 0.65)
            ingredientRows.append(row)
            #destroy and place the add button at the new bottom row 
            addIngredientRowButton.destroy()
            addIngredientRowButton = tk.Button(master = ingredientRows[2], command = addIngredientRow, text = '+',width = 4, height = 2)
            addIngredientRowButton.grid(column = 12, row = 0)
        elif len(ingredientRows) == 3:
            row = newIngredientRow()
            row.place(relx = .08, rely = 0.75)
            ingredientRows.append(row)
            addIngredientRowButton.destroy()
            addIngredientRowButton = tk.Button(master = ingredientRows[3], command = addIngredientRow, text = '+', width = 4, height = 2)
            addIngredientRowButton.grid(column = 12, row = 0)
        elif len(ingredientRows) == 4:
            #maximum number of rows added
            pass
        
    #creates all the widgets within a single row of ingredient entries and returns the frame
    def newIngredientRow():
        rowFrame = tk.Frame(master= window3, background = "#D8D7E8")
        global pairing
        columnNo = 0
        for i in range(4):
           #create combobox widget for ingredient, bind to functions, put in frame
           ingredientEntry = ttk.Combobox(rowFrame, width = 10, textvariable=tk.StringVar(), values=[' + New Ingredient'], style = "TCombobox")
           ingredientEntry.bind('<Button>', enterValue)
           ingredientEntry.bind('<<ComboboxSelected>>', checkForModuleChange)           
           ingredientEntry.grid(row=0, column = columnNo, padx = 10)
           #create search button widget, link with combobox above, bind to functions, put in frame
           searchButton = tk.Button(rowFrame, text='Search')
           searchButton.grid(row=0, column = columnNo+1)
           searchButton.bind('<Button>', enterValue)
           searchButton.bind('<Button>', searchForIngredient)
           pairing[searchButton] = ingredientEntry
           #create entry widget for quantity, bind to functions, put in frame, insert format placeholder
           quantityEntry = tk.Entry(rowFrame, width = 10, fg = '#D7D7D7')
           quantityEntry.bind('<Button>', enterValue)
           quantityEntry.insert(0, ' Qty')
           quantityEntry.grid(row=0, column = columnNo+2, padx = 10)
           columnNo = columnNo + 3
        #return the frame with all the widgets in
        return rowFrame

    #triggered when a recipe is selected so page widgets can be reset if needed
    def recipeSelected(event):
        global recipeNameCombo
        global newRecipeNameLabel
        global newRecipeNameEntry
        global initialBatchSizeEntry
        global ingredientRows
        global batchAdded
        batchAdded = False
        if recipeNameCombo.get() == ' + New Recipe':
            #show new name entry fields
            newRecipeNameLabel.grid(row = 0, column = 3, padx = 20)
            newRecipeNameEntry.grid(row = 0, column = 4)
            #allow user to enter initial batch size for recipe
            initialBatchSizeEntry.configure(state="normal")
            initialBatchSizeEntry.delete(0, tk.END)
            for row in ingredientRows:
                        for item in row.children.items():
                            #clear contents of any previously filled widgets
                            if item[1].winfo_class() == 'TCombobox':
                                item[1].set('')
                            elif item[1].winfo_class() == 'Entry':
                                item[1].delete(0, tk.END)
                                item[1].configure(fg = '#D7D7D7')
                                item[1].insert(0, ' Qty')
        else:
            #existing recipe selected so remove new name fields
            newRecipeNameLabel.grid_remove()
            newRecipeNameEntry.grid_remove()
            recipe = recipeNameCombo.get()
            #display initial batch size - batch size stored with lowest value batchID - then disable widget 
            mycursor.execute("SELECT BatchSizeName, BatchID FROM tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipe + "' AND tblBaseRecipe.RecipeID = tblBatchSize.RecipeID LIMIT 1")
            initialBatchSizeEntry.delete(0, tk.END)
            record = mycursor.fetchall()[0]
            batchName = record[0]
            batchID = record[1]
            initialBatchSizeEntry.insert(0, batchName)
            initialBatchSizeEntry.configure(state="disabled")
            #fetch all ingredients and quantities from database for this order's initial batch size
            mycursor.execute("SELECT IngredientName, Quantity FROM tblBaseIngredient, tblIngredientInBatchSize WHERE BatchID = " + str(batchID) + " AND tblIngredientInBatchSize.IngredientID = tblBaseIngredient.IngredientID")
            records = mycursor.fetchall()
            #add widget rows if needed to fit all ingredients
            if len(records)>8:
                addIngredientRow()
            if len(records)>12:
                addIngredientRow()
            count = 0
            #insert names and quantities into widgets 
            for row in ingredientRows:
                        for item in row.children.items():
                            if item[1].winfo_class() == 'TCombobox':
                                try:
                                    #insert name into ingredient widget
                                    ingredientName = records[count][0]
                                    item[1].set(ingredientName)
                                except:
                                    #no more stored ingredients to insert
                                    item[1].set('')
                            elif item[1].winfo_class() == 'Entry':
                                try:
                                    #insert quantity into corresponding widget
                                    ingredientQuantity = records[count][1]
                                    item[1].delete(0, tk.END)
                                    item[1].configure(fg = 'black')
                                    item[1].insert(0, ingredientQuantity)
                                    #increment counter for next stored ingredient
                                    count = count + 1
                                except:
                                    #no more stored quantities to insert
                                    item[1].delete(0, tk.END)
                                    item[1].configure(fg = '#D7D7D7')
                                    item[1].insert(0, ' Qty')
                
    global recipeNameCombo
    global newRecipeNameLabel
    global newRecipeNameEntry
    global newRecipeFlag

    #create widgets for first row of page
    row1Frame = tk.Frame(master = window3, bg = '#D8D7E8')
    recipeNameLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="Recipe Name", font=("Arial", 20))
    recipeNameLabel.grid(row=0, column =0, padx = (0,20))
    recipeNameCombo = ttk.Combobox(row1Frame, textvariable=tk.StringVar(), width = 50, values=[' + New Recipe'], style = "TCombobox")
    #check if new recipe is immediately being entered when called from another page with '+ New Recipe'
    if newRecipeFlag == True:
        recipeNameCombo.insert(0, ' + New Recipe')
        #trigger recipeSelected function to show new fields as soon as new window opened
        recipeNameCombo.bind('<Map>', recipeSelected)
    recipeNameCombo.grid(row=0, column =1)
    recipeNameCombo.bind('<<ComboboxSelected>>', recipeSelected)
    #create search button and link to recipeName combobox widget
    searchButton = tk.Button(row1Frame, text='Search')
    searchButton.grid(row=0, column =2)
    global pairing
    pairing[searchButton] = recipeNameCombo
    searchButton.bind('<Button>', enterValue)
    searchButton.bind('<Button>', searchForRecipe)
    #create widgets for new recipe name but don't display immediately 
    newRecipeNameLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="New Recipe Name", font=("Arial", 20))
    newRecipeNameEntry = tk.Entry(row1Frame, width = 40)
    row1Frame.place(relx = .09, rely = .205)

    #create widgets for second row of page - intial batch size field
    global initialBatchSizeEntry
    row2Frame = tk.Frame(master= window3, background = "#D8D7E8")
    initialBatchSizeClarifyButton = tk.Button(master=row2Frame, command = initialClarifyPopup, width = 4, height = 2, text = '?')
    initialBatchSizeClarifyButton.grid(row=0, column = 0, padx = (0,20))
    initialBatchSizeClarifyButton.bind('<Button>', enterValue)
    initialBatchSizeLabel = tk.Label(master=row2Frame, fg = "#4F2C54", background = "#D8D7E8", text= "Initial " + "\n" + "Batch Size", font=("Arial", 20), justify = 'right')
    initialBatchSizeLabel.grid(row = 0, column = 1)
    initialBatchSizeEntry = tk.Entry(row2Frame, width = 120, state='disabled', fg = 'black')
    initialBatchSizeEntry.bind('<Button>', enterValue)
    initialBatchSizeEntry.grid(row=0, column = 2, padx = (40, 0))
    row2Frame.place(relx = .06, rely = .28)

    #create widgets for third row of page - 'title' for ingredients in recipe
    row3Frame = tk.Frame(master= window3, background = "#D8D7E8")
    ingredientsLabel = tk.Label(master=row3Frame, fg = "#4F2C54", background = "#D8D7E8", text= "Ingredients and Quantities", font=("Arial", 20), justify = 'center')
    ingredientsLabel.pack()
    row3Frame.place(relx = .5, rely = .4, anchor = 'c')

    #initialise ingredient rows array to store all rows of widgets 
    global ingredientRows
    ingredientRows = []
    y = 0.45
    #create and place 2 ingredient entry rows on page to start with
    for i in range (2):
        rowFrame = newIngredientRow()
        rowFrame.place(relx = .08, rely = y)
        y = y + 0.1
        ingredientRows.append(rowFrame)

    #create '+' button for new ingredient rows within frame of bottom row 
    global addIngredientRowButton
    addIngredientRowButton = tk.Button(master = ingredientRows[1], command = addIngredientRow, width = 4, height = 2, text = '+')
    addIngredientRowButton.grid(column = 12, row = 0)

    #create widgets for bottom row (buttons) of page
    bottomFrame = tk.Frame(master=window3)
    bottomFrame.configure(pady=50, background = "#D8D7E8")
    #button to validate and save user's entries for recipe when all fields entered
    confirmButtonBorder = tk.Frame(bottomFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, command = validate, text="Confirm",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.grid(column=0, row = 0)
    #button to cancel recipe entry
    cancelButtonBorder = tk.Frame(bottomFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    cancelButton = tk.Button(master=cancelButtonBorder, text="Cancel", activeforeground='white', fg = "#273A36", command = closeModule, font = ("Arial", 25), highlightbackground = '#C6D8D9')
    cancelButton.pack()
    cancelButtonBorder.grid(column=1, row = 0, padx = 40)
    bottomFrame.place(relx=.40, rely=.78)

    #if page should be opening in new window, open window on top of previous one and pass execution to it
    if newWindowFlag == True:
        window3.geometry("1400x800+110+20")
        window3.configure(background = "#D8D7E8")
        window3.mainloop()

#create and display window to allow user to choose to add/edit another batch size for this recipe
def batchSizePopup():
    #create alert window and pass execution to it
    global batchSizePopupWindow
    global window3
    batchSizePopupWindow = tk.Toplevel()
    window3.grab_release()
    batchSizePopupWindow.grab_set()

    #triggered when 'NO' button is pressed for another batch size, closing the popup AND recipe page 
    def closeBatchSizePopup():
        global batchSizePopupWindow
        global previous
        global welcomeWindow
        global batchAdded
        global includeInitial
        batchAdded = False
        #close popup
        batchSizePopupWindow.grab_release()
        batchSizePopupWindow.destroy()
        global newWindowFlag
        global window3
        #check if recipe page was opened in new window 
        if newWindowFlag == True and len(previous) != 1:
            global newRecipeNameEntry
            if newRecipeNameEntry.winfo_ismapped() == True:
                #fetch new recipe name 
                newRecipe = newRecipeNameEntry.get()
            else:
                newRecipe = recipeCombo.get()
            #place name in widget on page it was called from 
            for widget in welcomeWindow.winfo_children():
                if widget.winfo_class() == 'Frame':
                    for item in widget.winfo_children():
                        try:
                            if item.get() == ' + New Recipe':
                                item.delete(0, tk.END)
                                item.insert(0, newRecipe)
                        except:
                            pass
            #close new window and return execution
            includeInitial = True
            window3.grab_release()
            window3.destroy()
            previous.pop()
        else:
            #if on original page, this recipe page can only have been called from homepage so return to homepage
            includeInitial = True
            newWindowFlag == False
            homepage()

    #create and place title question for popup
    row1Frame = tk.Frame(master= batchSizePopupWindow, background = "#C6D8D9")
    alertLabel = tk.Label(master=row1Frame, fg = "#273A36", background = "#C6D8D9", text="Add/edit another batch size " + "\n" + "for this recipe?", font=("Arial", 20))
    alertLabel.pack()
    row1Frame.place(relx = .5, rely = .17, anchor = 'c')

    #create and place yes and no buttons linked to correct functions
    buttonFrame = tk.Frame(master=batchSizePopupWindow)
    buttonFrame.configure(background = "#C6D8D9")
    yesButtonBorder = tk.Frame(buttonFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    yesButton = tk.Button(master=yesButtonBorder, text="Yes",  fg = "#273A36", command = addBatchSize, activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
    yesButton.pack()
    yesButtonBorder.grid(column=0, row = 0)
    noButtonBorder = tk.Frame(buttonFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    noButton = tk.Button(master=noButtonBorder, text="No", command = closeBatchSizePopup, activeforeground='white', fg = "#273A36", font = ("Arial", 25), highlightbackground = '#C6D8D9')
    noButton.pack()
    noButtonBorder.grid(column=1, row = 0, padx = 20)
    buttonFrame.place(relx=.35, rely=.57)

    #display popup window and pass execution to it 
    batchSizePopupWindow.geometry("500x200+440+260")
    batchSizePopupWindow.configure(background = "#C6D8D9")
    batchSizePopupWindow.mainloop()
           
#displays batch size entry page 
def addBatchSize():

    #allows user to fully logout if this page has been opened in a new window 
    def logOutFromNewWindow():
        global newWindowFlag
        newWindowFlag = False
        win = changeScreen()
        window.destroy()
        registration_login()

    global recipeCombo
    global recipeForNewBatchSize
    global batchSizePopupWindow
    #destroys popup window if coming from recipe page
    try:
        batchSizePopupWindow.grab_release()
        batchSizePopupWindow.destroy()
    except:
        pass

    #create new window and recreate logout/info buttons and title - batch size page ALWAYS on top of another window
    global newWindowFlag
    window = tk.Toplevel()
    window.title("Batch Size Window")
    window.grab_set()
    newlogOutButtonBorder = tk.Frame(master=window, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    newlogOutButton = tk.Button(master=newlogOutButtonBorder, command = logOutFromNewWindow, justify = 'center', text = '-->', width = 7, height = 4)
    newlogOutButton.pack()
    newlogOutButtonBorder.place(relx = .05, rely = .06)
    newtitle = tk.Label(master=window, fg = "#4F2C54", text = 'Add/Edit Batch Size', bg = "#D8D7E8", font=("Courier", 80))
    newtitle.place(relx =.5, rely = .1, anchor = 'c')
    newinfoButtonBorder = tk.Frame(master=window, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    newinfoButton = tk.Button(master=newinfoButtonBorder, command = infoPopup, text = "?", width = 2, font = ("Arial", 50),highlightbackground = '#C6D8D9')
    newinfoButton.pack()
    newinfoButtonBorder.place(relx = .85, rely = .06)

    #add window to previous array
    global previous
    if newWindowFlag == True:
        previous.append(welcomeWindow)
    else:
        previous = [welcomeWindow]
    global infoButtonMessage
    infoButtonMessage = 'batchSizes'

    #triggered when batch size is fully validated or cancelled, and page needs to be closed
    def closeModule():
        global previous
        global newWindowFlag
        global newBatchNameEntry
        #check if PREVIOUS page was opened in new window 
        if newWindowFlag == True:
            if newBatchNameEntry.winfo_ismapped() == True:
                #fetch new recipe name 
                newBatch = newBatchNameEntry.get()            
            else:
                newBatch = batchCombo.get()
            #place name in widget on page it was called from 
            for widget in previous[len(previous)-2].winfo_children():
                    if widget.winfo_class() == 'Frame':
                        for item in widget.winfo_children():
                            try:
                                if item.get() == ' + New Batch Size':
                                    item.delete(0, tk.END)
                                    item.insert(0,newBatch)
                            except:
                                pass
        #close new window and return execution
            previous.pop()
        newWindowFlag = False
        window.grab_release()
        window.destroy()
        
    #fetch initial batch size ID for recipe and use to find all ingredients included in recipe
    global ingredients
    global quantities
    mycursor.execute("SELECT BatchID from tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipeForNewBatchSize + "' AND tblBaseRecipe.RecipeID = tblBatchSize.RecipeID LIMIT 1")
    global batchID
    batchID = mycursor.fetchall()[0][0]
    mycursor.execute("SELECT IngredientName, Quantity from tblIngredientInBatchSize, tblBaseIngredient WHERE BatchID = " + str(batchID) + " AND tblBaseIngredient.IngredientID = tblIngredientInBatchSize.IngredientID")
    records = mycursor.fetchall()
    ingredients =[]
    quantities = []
    #set the first ingredient and quantity to act as the displayed scaling example
    for ingredient in records:
        if 'firstIngredient' not in locals():
            firstIngredient = ingredient[0]
            firstQuantity = ingredient[1]
        ingredients.append(ingredient[0])
        quantities.append(ingredient[1])

    #validates all entered fields and updates database
    def validate():
        invalidFields = []
        #checking batch size field
        global batchCombo
        global recipeForNewBatchSize
        batchSizeEntered = batchCombo.get()
        mycursor.execute("SELECT BatchSizeName FROM tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipeForNewBatchSize + "' AND tblBaseRecipe.RecipeID = tblBatchSize.RecipeID")
        flag = False
        if (batchSizeEntered == ' + New Batch Size'):
            flag = True
        else:
            for record in mycursor:
                #matches an existing batch size as needed
                if batchSizeEntered == record[0]:
                    flag = True

        #invalid if recipe entered by user is not stored in database or '+ New...'
        if flag == False:
            invalidFields.append('Batch Size')
        
        #checking new batch name field
        try:
            global newBatchNameEntry
            if (newBatchNameEntry.get().isspace() == True) or (newBatchNameEntry.get() == ''):
                #invalid if new recipe name left blank
                invalidFields.append('Batch Size Name')
        except:
            pass

        #checking conversion entry field
        global conversionQuantityEntry
        try:
            if (conversionQuantityEntry.get().isspace() == True) or (conversionQuantityEntry.get() == ''):
                #invalid if first ingredient scale field name left blank
                invalidFields.append('New Quantity of ' + firstIngredient)
        except:
            pass
        
        #checking ingredient fields
        try:
            global ingredientEntries
            for ingredientEntry in ingredientEntries:
                if (ingredientEntry[1].get().isspace() == True) or (ingredientEntry[1].get() == ''):
                    #invalid if any ingredient quantities left blank (all batches for same recipe should include same ingredients)
                    invalidFields.append('Quantity of ' + ingredientEntry[0].cget("text"))        
        except:
            pass

        global existingNameFlag
        global batchAdded
        existingNameFlag = False

        #display error message popup if any invalid fields were identified  
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            validationPopup(invalidFields)
        else:
            #save to database
            if batchSizeEntered == ' + New Batch Size':
                existingNameFlag = False
                #find recipe ID
                mycursor.execute("SELECT RecipeID FROM tblBaseRecipe WHERE RecipeName = '" + recipeForNewBatchSize + "'")
                recipeID = mycursor.fetchall()[0][0]
                batchEntered = newBatchNameEntry.get()
                #find all batches stored for this recipe already
                mycursor.execute("SELECT BatchSizeName from tblBatchSize WHERE RecipeID = "+ str(recipeID))
                storedBatches = mycursor.fetchall()
                for batch in storedBatches:
                    if batch[0] == batchEntered:
                        #new recipe name is already taken
                        existingNameFlag = True
                if existingNameFlag == True:
                    validationPopup('')
                else:
                    #attempt to add new batch size record to database for given recipe 
                    mycursor.execute("INSERT INTO tblBatchSize (RecipeID, BatchSizeName) VALUES  (" + str(recipeID) + ", '" + newBatchNameEntry.get() +"')")
                    mycursor.execute("SELECT BatchID FROM tblBatchSize WHERE BatchSizeName = '"+ newBatchNameEntry.get() + "' and RecipeID = "+ str(recipeID))
                    batchID = mycursor.fetchall()[0][0]
                    if existingNameFlag == False:
                        #new batch size name is valid and all other fields valid so save ingredients in batch size to database
                        for eachingredient in ingredientEntries:
                            ingredientName = eachingredient[0].cget("text")
                            mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '" + ingredientName + "'")
                            ingredientID = mycursor.fetchall()[0][0]
                            ingredientQuantity = eachingredient[1].get()
                            mycursor.execute("INSERT INTO tblIngredientInBatchSize VALUES (" + str(batchID) + ", " + str(ingredientID) + ", " + str(ingredientQuantity) + ")")
                            mydb.commit()
                            batchAdded = True
                        closeModule()
            else:
                #all fields valid - delete stored ingredients in batch size from database and rewrite
                mycursor.execute("SELECT RecipeID FROM tblBaseRecipe WHERE RecipeName = '" + recipeForNewBatchSize + "'")
                recipeID = mycursor.fetchall()[0][0]
                mycursor.execute("SELECT BatchID FROM tblBatchSize WHERE BatchSizeName = '" + batchSizeEntered + "' AND recipeID = " + str(recipeID))
                batchID = mycursor.fetchall()[0][0]
                mycursor.execute("DELETE FROM tblIngredientInBatchSize WHERE BatchID = " + str(batchID))
                #iterate through entered ingredients and add to database
                for eachingredient in ingredientEntries:
                        ingredientName = eachingredient[0].cget("text")
                        mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '" + ingredientName + "'")
                        ingredientID = mycursor.fetchall()[0][0]
                        ingredientQuantity = eachingredient[1].get()
                        mycursor.execute("INSERT INTO tblIngredientInBatchSize VALUES (" + str(batchID) + ", " + str(ingredientID) + ", " + str(ingredientQuantity) + ")")
                        mydb.commit()
                        batchAdded = True
                #re-calculate shopping dates for any orders including this batch
                mycursor.execute("SELECT OrderID FROM tblBatchSizeInOrder WHERE BatchID = " + str(batchID))
                orders = mycursor.fetchall()
                for order in orders:
                    initialShopDateScheduling(order[0])
                shoppingOptimisation()
                closeModule()

                        
    #creates and displays popup window to alert user of any invalid field entries on page        
    def validationPopup(invalidFields):
        global validationPopupWindow
        validationPopupWindow = tk.Toplevel()
        validationPopupWindow.grab_set()

        global existingNameFlag
        #change message depending on invalid fields
        try:
            if existingNameFlag == False:
                #format text so it fits in dimension of window and place
                clarificationText = textwrap.wrap("Please enter a valid " + invalidFields, width = 50, break_long_words = False, placeholder = '')
            else:
                clarificationText = textwrap.wrap("Batch size name is already taken for this recipe.", width = 50, break_long_words = False, placeholder = '')
        except:
            clarificationText = textwrap.wrap("Batch size name is already taken for this recipe.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=validationPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read warning message and place
        buttonsFrame = tk.Frame(master=validationPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeValidationPopup, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        validationPopupWindow.geometry("600x500+360+140")
        validationPopupWindow.configure(background = "#C6D8D9")
        validationPopupWindow.mainloop()
        
    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeValidationPopup():
        global validationPopupWindow
        validationPopupWindow.grab_release()
        validationPopupWindow.destroy()

    #triggered once batch size selected to show coversion scale widgets
    def showConversionFields(event):
        global ingredientEntries
        global editQuantitiesLabel
        global batchCombo
        global conversionQuantityLabel
        global conversionQuantityEntry
        global conversionEntryFrame
        global row2Frame
        global newBatchNameEntry
        global newBatchNameLabel
        #determine whether new batch size being added or existing one edited
        if batchCombo.get() == ' + New Batch Size':
            #show or hide new name widget if new batch or not
            try:
                #place new batch widgets if already exist
                newBatchNameLabel.grid(row = 0, column = 3)
                newBatchNameEntry.grid(row = 0, column = 4)
            except:
                #create and place widgets
                newBatchNameLabel = tk.Label(master=row2Frame, fg = "#4F2C54", background = "#D8D7E8", text="New Batch Size Name:" , font=("Arial", 20), justify = 'center')
                newBatchNameLabel.grid(row = 0, column = 3, padx = (30,0))
                newBatchNameEntry = tk.Entry(row2Frame, width = 20)
                newBatchNameEntry.grid(row=0, column = 4, padx = (30, 0))
        else:
            try:
                newBatchNameLabel.grid_remove()
                newBatchNameEntry.grid_remove()
            except:
                pass

        mycursor.execute("SELECT QuantityUnit FROM tblBaseIngredient WHERE IngredientName = '" + firstIngredient + "'")
        unit = mycursor.fetchall()[0][0]
            
        try:
            #place widgets if already exist
            initialQuantityLabel.place(relx = .5, rely = .35,  anchor='c')
            conversionEntryFrame.place(relx = .15, rely = .38)
        except:
            #fetch initial batch size name for recipe, create and place widgets
            global batchID
            mycursor.execute("SELECT BatchSizeName from tblBatchSize WHERE BatchID = " + str(batchID))
            initialBatchName = mycursor.fetchall()[0]
            initialQuantityLabel = tk.Label(master=window, fg = "#4F2C54", background = "#D8D7E8", text="Quantity of " + firstIngredient + " for " + str(initialBatchName[0]) + " is " + str(firstQuantity) + " (" + unit + "):" , font=("Arial", 20), justify = 'center')
            initialQuantityLabel.place(relx = .5, rely = .35,  anchor='c')

        try:
            #place widget if already exist
            conversionEntryFrame.place(relx = .15, rely = .38)
        except:
            #create and place widgets
            batchSizeChosen = batchCombo.get()
            conversionEntryFrame = tk.Frame(master= window, background = "#D8D7E8")
            conversionQuantityLabel = tk.Label(master=conversionEntryFrame, fg = "#4F2C54", background = "#D8D7E8", text="Please enter quantity of " + firstIngredient + " needed for " + batchSizeChosen + " (" + unit + "):" , font=("Arial", 20), justify = 'center')
            conversionQuantityLabel.grid(row = 0, column = 0)
            conversionQuantityEntry = tk.Entry(conversionEntryFrame, width = 20)
            conversionQuantityEntry.grid(row=0, column = 1, padx = (30, 0))
            convertButton = tk.Button(conversionEntryFrame, text='Convert',  command = showOtherFields)
            convertButton.grid(row=0, column = 2, padx = (3,0))
            conversionEntryFrame.place(relx = .15, rely = .38)

        #fetch batch size chosen to add/edit and display in conversion message
        batchSizeChosen = batchCombo.get()
        conversionQuantityLabel.configure(text="Please enter quantity of " + firstIngredient + " needed for " + batchSizeChosen + "(" + unit + "):")

        #destroy new quantity entries if any already on page until new scale entered
        try:
            editQuantitiesLabel.destroy()
        except:
            pass
        try:
            for ingredientEntry in ingredientEntries:
                ingredientEntry[0].destroy()
                ingredientEntry[1].destroy()
        except:
            pass
        
    #creates all the widgets within a single row of ingredient entries and returns the fram
    def newIngredientRow():
        rowFrame = tk.Frame(master= window, background = "#D8D7E8")
        global pairing
        global ingredients
        ingredientNo = 0
        global ingredientEntries
        ingredientEntries = []
        #calculate how many rows of up to 4 entry widgets are needed, and how many widgets in last row
        if len(ingredients)%4 == 0:
            rows = len(ingredients)//4
            lastRow = 4
        else:
            rows = (len(ingredients)//4)+1
            lastRow = len(ingredients)%4
        column = 0
        #create full rows of 4
        for row in range (rows-1):
            column = 0
            for i in range (4):
                #create label with each ingredient name in recipe
                ingredientLabel = tk.Label(master=rowFrame, fg = "#4F2C54", background = "#D8D7E8", text=ingredients[ingredientNo], font=("Arial", 20))
                ingredientLabel.grid(row = row, column = column, pady = 10)
                #create entry box for quantity of ingredient
                ingredientEntry = tk.Entry(rowFrame, width = 10)
                ingredientEntry.grid(row=row, column = column+1, padx = 10, pady = 10)
                ingredientNo += 1
                column +=2
                #store each ingredient quantity pair in array
                ingredientEntries.append([ingredientLabel, ingredientEntry])
        column = 0
        #create last row of up to 4
        for i in range (lastRow):
            if 'row' not in locals():
                row = 0
            #create label with each ingredient name in recipe
            ingredientLabel = tk.Label(master=rowFrame, fg = "#4F2C54", background = "#D8D7E8", text=ingredients[ingredientNo], font=("Arial", 20))
            ingredientLabel.grid(row = row+1, column = column, pady = 10)
            #create entry box for quantity of ingredient
            ingredientEntry = tk.Entry(rowFrame, width = 10)
            ingredientEntry.grid(row=row+1, column = column+1, padx = 10, pady = 10)
            ingredientNo += 1
            column +=2
            #store each ingredient quantity pair in array
            ingredientEntries.append([ingredientLabel, ingredientEntry])
        return rowFrame        

    #triggered when conversion scale widget is filled and entered to display other ingredients
    def showOtherFields():
        #destroy label if on page from a previous selection
        global editQuantitiesLabel
        try:
            editQuantitiesLabel.destroy()
        except:
            pass
        global newBatchNameEntry
        #fetch batch name depending on new or existing
        try:
            if newBatchNameEntry.winfo_ismapped() == True:
                batchEntered = newBatchNameEntry.get()
            else:
                batchEntered = batchCombo.get()
        except:
            batchEntered = batchCombo.get()

        #fetch new entered quantity of first ingredient in recipe
        newConversionQuantity = conversionQuantityEntry.get()
        floatFlag = isfloat(newConversionQuantity)
        global existingNameFlag
        existingNameFlag = False
        if floatFlag == False:
            validationPopup('New Quantity of ' + firstIngredient)
        else:
            #calculate scale for this amount from amount in INITIAL batch size of recipe
            batchSizeMultiplier = float(newConversionQuantity)/firstQuantity
            #display message to edit ingredients and ingredient entry widgets 
            editQuantitiesLabel = tk.Label(master=window, fg = "#4F2C54", background = "#D8D7E8", text="Edit any quantities that are incorrect for " + batchEntered, font=("Arial", 20), justify = 'center')
            editQuantitiesLabel.place(relx = .5, rely = .50,  anchor='c')
            ingredientsFrame = newIngredientRow()
            ingredientsFrame.place(relx = .15, rely = .52)
            #apply this scaling to each ingredient quantity in initial batch size and insert into widgets for user to edit if needed
            for i in range (len(ingredientEntries)):
                newQuantity = quantities[i] * batchSizeMultiplier
                ingredientEntries[i][1].delete(0, tk.END)
                ingredientEntries[i][1].insert(0, str(newQuantity))

    #create and display recipe name widgets, and disable (user can't change recipe the batch size is for without going back to recipe page)        
    row1Frame = tk.Frame(master= window, background = "#D8D7E8")
    recipeNameLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="Recipe Name", font=("Arial", 20))
    recipeNameLabel.grid(row = 0, column = 0)
    recipeNameEntry = tk.Entry(row1Frame, width = 100)
    recipeNameEntry.insert(0, recipeForNewBatchSize)
    recipeNameEntry.configure(state='disabled')
    recipeNameEntry.grid(row=0, column =1, padx = (30, 0))
    row1Frame.place(relx = .09, rely = .19)
    
    #create and display second row widgets (batch size name to add/edit)
    global batchCombo
    global row2Frame
    row2Frame = tk.Frame(master= window, background = "#D8D7E8")
    batchLabel = tk.Label(master=row2Frame, fg = "#4F2C54", background = "#D8D7E8", text="Batch Size", font=("Arial", 20))
    batchLabel.grid(row=0, column = 0, padx = (30,0))
    searchButton = tk.Button(row2Frame, text='Search')
    searchButton.grid(row=0, column = 2, padx = (3,0))
    searchButton.bind('<Button>', searchForBatchSize)
    #set flag to False - the user should not be able to edit the INITIAL batch size of recipe as this muct be done in the 'Add/Edit Base Recipe' page
    global includeInitial
    includeInitial = False
    batchCombo = ttk.Combobox(row2Frame, textvariable=tk.StringVar(), width = 25, values=[' + New Batch Size'], style = "TCombobox")
    batchCombo.bind('<<ComboboxSelected>>', showConversionFields)
    pairing[searchButton] = batchCombo
    #check if new batch is immediately being entered when called from another page with '+ New Batch Size'
    global newBatchFlag
    if newBatchFlag == True:
        batchCombo.insert(0, ' + New Batch Size')
        #trigger showConversionFields function to show new fields as soon as new window opened
        batchCombo.bind('<Map>', showConversionFields)
    batchCombo.grid(row=0, column = 1, padx = (39,0))
    row2Frame.place(relx = .09, rely = .26)

    #create widgets for bottom row (buttons) of page
    row7Frame = tk.Frame(master=window)
    row7Frame.configure(pady=50, background = "#D8D7E8")
    #button to validate and save user's entries for recipe when all fields entered
    confirmButtonBorder = tk.Frame(row7Frame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, text="Confirm",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), command = validate, highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.grid(column=0, row = 0)
    #button to cancel recipe entry
    cancelButtonBorder = tk.Frame(row7Frame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    cancelButton = tk.Button(master=cancelButtonBorder, command = closeModule, text="Cancel", activeforeground='white', fg = "#273A36",   font = ("Arial", 25), highlightbackground = '#C6D8D9')
    cancelButton.pack()
    cancelButtonBorder.grid(column=1, row = 0, padx = 40)
    row7Frame.place(relx=.40, rely=.77)

    #open window on top of previous one (ALWAYS base recipe page) and pass execution to it
    window.geometry("1400x800+110+20")
    window.configure(background = "#D8D7E8")
    window.mainloop()

#displays base ingredient entry page
def addIngredient():

    #allows user to fully logout if this page has been opened in a new window
    def logOutFromNewWindow():
        global previous
        global newWindowFlag
        newWindowFlag = False
        length = len(previous)
        for i in range (length-1):
            win = changeScreen()
            win.destroy()
        registration_login()

    #bug - need to change page explanation for all pages (+ clarify buttons??)
    #call change screen module once page opened 
    win = changeScreen()
    global newWindowFlag
    global previous
    global window1
    #determine whether page needs opening in a new window or existing one
    if newWindowFlag == False:
        window1 = welcomeWindow
        #destroy all widgets on page except login/info buttons and title
        for widget in window1.winfo_children():
            global logOutButtonBorder
            global infoButtonBorder
            global title
            if widget != logOutButtonBorder and  widget != title and  widget != infoButtonBorder:
                widget.destroy()
            #set title widget to correct text
            title.configure(text = 'Add/Edit Ingredient')
            title.place(relx =.5, rely = .1, anchor = 'c')
    else:
        #create new window, pass execution and recreate logout/info buttons and title
        window1 = tk.Tk()
        try:
            previous[len(previous)-1].grab_release()
        except:
            pass
        window1.grab_set()
        window1.attributes('-topmost', True)
        newlogOutButtonBorder = tk.Frame(master=window1, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        newlogOutButton = tk.Button(master=newlogOutButtonBorder, command = logOutFromNewWindow, justify = 'center', text = '-->', width = 7, height = 4)
        newlogOutButton.pack()
        newlogOutButtonBorder.place(relx = .05, rely = .06)
        newtitle = tk.Label(master=window1, fg = "#4F2C54", text = 'Add/Edit Ingredient', bg = "#D8D7E8", font=("Courier", 80))
        newtitle.place(relx =.5, rely = .1, anchor = 'c')
        newinfoButtonBorder = tk.Frame(master=window1, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        newinfoButton = tk.Button(master=newinfoButtonBorder, text = "?", width = 2, font = ("Arial", 50),highlightbackground = '#C6D8D9')
        newinfoButton.pack()
        newinfoButtonBorder.place(relx = .85, rely = .06)
        
    #triggered when all validation done or cancel button pressed to close page and pass back execution
    def closeModule():
        global previous
        global newWindowFlag
        if newWindowFlag == True:
            #fetches ingredient name and passes back to page it was called from
            if newIngredientNameEntry.winfo_ismapped() == True:
                newIngredient = newIngredientNameEntry.get()            
            else:
                newIngredient = combo.get()
            for widget in previous[len(previous)-2].winfo_children():
                    if widget.winfo_class() == 'Frame':
                        for item in widget.winfo_children():
                            try:
                                if item.get() == ' + New Ingredient':
                                    item.delete(0, tk.END)
                                    item.insert(0,newIngredient)
                            except:
                                pass
                            for item2 in item.winfo_children():
                                for item3 in item2.winfo_children():
                                    for item4 in item3.winfo_children():
                                        try:
                                            if item4.get() == ' + New Ingredient':
                                                item4.delete(0, tk.END)
                                                item4.insert(0,newIngredient)
                                        except:
                                            pass
            #close new window and return execution
            window1.grab_release()
            window1.destroy()
            previous.pop()
        else:
            #if on original page, this recipe page can only have been called from homepage so return to homepage
            newWindowFlag == False
            homepage()


    #display explanation popup window for entering units when user clicks '?' button 
    def unitClarifyPopup():
        global unitClarifyPopupWindow
        unitClarifyPopupWindow = tk.Toplevel()
        unitClarifyPopupWindow.grab_set()

        #format text so it fits in dimension of window and place
        clarificationText = textwrap.wrap("This should be the unit you ALWAYS measure this ingredient in (eg. ml, g, oz), which will apply to all quantities used of this ingredient (in recipes, stock etc). You don't need to enter this unit when entering quantities, as it will use the unit you enter here. ", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=unitClarifyPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
                clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
                clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=unitClarifyPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeUnitClarify, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        unitClarifyPopupWindow.geometry("600x500+360+140")
        unitClarifyPopupWindow.configure(background = "#C6D8D9")
        unitClarifyPopupWindow.mainloop()

    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeUnitClarify():
        global unitClarifyPopupWindow
        unitClarifyPopupWindow.grab_release()
        unitClarifyPopupWindow.destroy()

    #display explanation popup window for entering purchasable quantities when user clicks '?' button 
    def purchasableClarifyPopup():
        global purchasableClarifyPopupWindow
        purchasableClarifyPopupWindow = tk.Toplevel()
        purchasableClarifyPopupWindow.grab_set()

        #format text so it fits in dimension of window and place
        clarificationText = textwrap.wrap("Purchasable quantities are the amounts you can buy in the shops (eg. 2kg bag of flour). This MUST match the unit entered for this ingredient, and only contain the number (eg. if you entered 'g' as the unit, just put 2000, not 2 or 2kg or 2000g). Press the '+' button to add more if needed, and please enter all possible options.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=purchasableClarifyPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
                clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
                clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=purchasableClarifyPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closePurchasableClarify, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        purchasableClarifyPopupWindow.geometry("600x500+360+140")
        purchasableClarifyPopupWindow.configure(background = "#C6D8D9")
        purchasableClarifyPopupWindow.mainloop()

    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closePurchasableClarify():
        global purchasableClarifyPopupWindow
        purchasableClarifyPopupWindow.grab_release()
        purchasableClarifyPopupWindow.destroy()


    #name window and add as previous window 
    window1.title("Ingredient Window")
    if newWindowFlag == True:
        previous.append(window1)
    else:
        previous = [window1]
    global infoButtonMessage
    infoButtonMessage = 'baseIngredients'

    #validates all entered fields and updates database
    def validate():
        invalidFields = []
        global existingIngredientFlag
        
        #checking ingredient name field
        ingredientEntered = combo.get()
        mycursor.execute("SELECT IngredientName FROM tblBaseIngredient")
        flag = False
        if ingredientEntered == ' + New Ingredient':
            flag = True
        else:
            for record in mycursor:
                if ingredientEntered == record[0]:
                    #matches an existing ingredient as needed
                    flag = True

        #determines whether an ingredient has been selected by checking if the selection has triggered the shelf life widget to be displayed yet          
        global shelfLifeEntry
        try:
            if shelfLifeEntry.winfo_ismapped() == False:
                flag = False
        except:
            flag = False

        if flag == False:
            #display error message if no ingredient name selected
            invalidFields.append('Ingredient Name')
            invalidFields = ', '.join(invalidFields)
            existingIngredientFlag = False
            validationPopup(invalidFields)
        
        #checking new ingredient name field when '+ New Ingredient' chosen
        global recipeForNewBatchSize
        if newIngredientNameEntry.winfo_ismapped() == True:
            ingredientEntered = newIngredientNameEntry.get()
            #invalid if new recipe name left blank
            if (ingredientEntered.isspace() == True) or (ingredientEntered == ''):
                invalidFields.append('New Ingredient Name')

        #checking purchasable quantity fields
        global qtyEntries
        noPurchasableQtyFlag = True
        purchasableQtys = []
        for entry in qtyEntries:
            #fetch each entered purchasable quantity from page
            purchasableQtyEntered = entry.get()
            if (purchasableQtyEntered.isspace() == False) and (purchasableQtyEntered != '') and (purchasableQtyEntered != ' Qty'):
                floatFlag = isfloat(purchasableQtyEntered)
                if floatFlag == False:
                    #invalid if not a float
                    invalidFields.append('Purchasable Quantity')
                else:
                    #quantity is not blank and IS a float so valid - add to array and set flag to True
                    purchasableQtys.append(purchasableQtyEntered)
                    noPurchasableQtyFlag = False

        #invalid as at least one purchasable quantity must be entered per recipe
        if noPurchasableQtyFlag == True:
            invalidFields.append('At least one purchasable quantity')

        #checking shelf life field
        shelfLifeEntered = shelfLifeEntry.get()
        floatFlag = isfloat(shelfLifeEntered)
        if (shelfLifeEntered.isspace() == True) or (shelfLifeEntered == '') or (floatFlag == False):
                #invalid if blank or not a float            
                invalidFields.append('Shelf Life')

        #checking quantities in stock fields
        global qtyInStockRows
        for row in qtyInStockRows:
                for i in range (len(row.winfo_children())):
                        #only check the row widgets once, at the start of each row
                        if i==0:
                            #fetch each entered stock quantity and expiry date pair from page
                            stockQtyEntered = row.winfo_children()[1].get()
                            expiryEntered = row.winfo_children()[3].get()
                            if stockQtyEntered == '' or stockQtyEntered.isspace() == True:
                                if expiryEntered == '' or expiryEntered.isspace() == True or expiryEntered == ' DD/MM/YYYY':
                                    pass
                                else:
                                    #invalid if quantity left blank but expiry date is not
                                    invalidFields.append('Quantity for expiry date of '+ str(expiryEntered))
                            else:
                                floatFlag = isfloat(stockQtyEntered)
                                if floatFlag == False:
                                    #invalid if quantity is not a float
                                        invalidFields.append('Stock Quantity')
        
                            if expiryEntered == '' or expiryEntered.isspace() == True or expiryEntered == ' DD/MM/YYYY':
                                if stockQtyEntered == '' or stockQtyEntered.isspace() == True:
                                    pass
                                else:
                                    #invalid if expiry date left blank but quantity is not
                                    invalidFields.append('Expiry date for stock amount of '+ str(stockQtyEntered))
                            else: 
                                try:
                                    date = datetime.strptime(expiryEntered, "%d/%m/%Y")
                                    #invalid if expiry date is before today's date
                                    if date.date() < today:
                                        invalidFields.append('Expiry date')
                                except ValueError:
                                    #invalid if expiry date is not a valid date in correct format
                                    invalidFields.append('Expiry Date')
                                

        #initialise flag    
        existingIngredientFlag = False
        
        #display error message popup if any invalid fields were identified 
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            validationPopup(invalidFields)
        else:
            #fetch ingredient unit from page
            global unitEntry
            unitEntered = unitEntry.get()
            #check new ingredient name chosen is not already taken by a stored ingredient
            if combo.get() == ' + New Ingredient':
                #check new name is not already a used name
                mycursor.execute("SELECT IngredientName FROM tblBaseIngredient")
                allingredients = mycursor.fetchall()
                ingredientEntered = newIngredientNameEntry.get()
                for ingredient in allingredients:
                    if ingredientEntered == ingredient[0]:
                        existingIngredientFlag = True
                        #display error message
                        validationPopup('')
                if existingIngredientFlag == False:
                    #all fields valid - save new ingredient and corresponding values to database
                    #add ingredient record
                    mycursor.execute("INSERT INTO tblBaseIngredient (IngredientName, ShelfLife, AvgWeeklyDemand, QuantityUnit) VALUES ('" + ingredientEntered + "', '" + shelfLifeEntered + "', 0, '" + unitEntered + "')")
                    mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '"+ ingredientEntered + "'")
                    ingredientID = mycursor.fetchall()[0][0]
                    #add purchasable quantities to database with ingredient just entered
                    for quantity in purchasableQtys:
                        mycursor.execute("INSERT INTO tblPuchasableQuantity VALUES ('" + str(ingredientID) + "', '" + str(quantity) + "')")
                    #add quantities in stock and corresponding expiry dates to database with ingredient just entered
                    for row in qtyInStockRows:
                        for i in range (len(row.winfo_children())):
                            if i==0:
                                stockQtyEntered = row.winfo_children()[1].get()
                                expiryEntered = row.winfo_children()[3].get()
                                if stockQtyEntered != '' and stockQtyEntered.isspace() == False:
                                    expiryEntered = datetime.strptime(expiryEntered, "%d/%m/%Y")
                                    mycursor.execute("INSERT INTO tblItemsInStock VALUES ('" + str(ingredientID) + "', '" + stockQtyEntered + "', '" + str(expiryEntered) + "')")
                    mydb.commit()
                    closeModule()

            else:
                #all fields valid - update stored ingredient in database
                mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '"+ ingredientEntered + "'")
                ingredientID = mycursor.fetchall()[0][0]
                mycursor.execute("UPDATE tblBaseIngredient SET IngredientName = '" + ingredientEntered + "', ShelfLife = '" + shelfLifeEntered + "', QuantityUnit = '" + unitEntered + "' WHERE IngredientID = '" + str(ingredientID) + "'")
                #delete purchasable quantities and items in stock using this ingredient ID
                mycursor.execute("DELETE FROM tblItemsInStock WHERE IngredientID = " + str(ingredientID))
                mycursor.execute("DELETE FROM tblPuchasableQuantity WHERE IngredientID = " + str(ingredientID))
                #rewrite purchasable quantities
                for quantity in purchasableQtys:
                    mycursor.execute("INSERT INTO tblPuchasableQuantity VALUES ('" + str(ingredientID) + "', '" + str(quantity) + "')")
                #rewrite items in stock
                for row in qtyInStockRows:
                    for i in range (len(row.winfo_children())):
                        if i==0:
                            stockQtyEntered = row.winfo_children()[1].get()
                            expiryEntered = row.winfo_children()[3].get()
                            if stockQtyEntered != '' and stockQtyEntered.isspace() == False:
                                expiryEntered = datetime.strptime(expiryEntered, "%d/%m/%Y")
                                mycursor.execute("INSERT INTO tblItemsInStock VALUES ('" + str(ingredientID) + "', '" + stockQtyEntered + "', '" + str(expiryEntered) + "')")
                mydb.commit()
                #re-calculate shopping dates for any orders including this ingredient
                mycursor.execute("SELECT OrderID FROM tblBaseIngredientInOrder WHERE IngredientID = " + str(ingredientID))
                orders = []
                for order in mycursor:
                    if order[0] not in orders:
                        orders.append(order[0])
                mycursor.execute("SELECT OrderID FROM tblBatchSizeInOrder, tblIngredientInBatchSize WHERE IngredientID = " + str(ingredientID) + " and tblIngredientInBatchSize.BatchID = tblBatchSizeInOrder.BatchID")
                for order in mycursor:
                    if order[0] not in orders:
                        orders.append(order[0])
                for order in orders:
                    initialShopDateScheduling(order)
                shoppingOptimisation()
                closeModule()


    #creates and displays popup window to alert user of any invalid field entries on page     
    def validationPopup(invalidFields):
        global validationPopupWindow
        validationPopupWindow = tk.Toplevel()
        global window1
        window1.grab_release()
        validationPopupWindow.grab_set()

        #change message depending on invalid fields
        global existingIngredientFlag
        if existingIngredientFlag != True:
            #format text so it fits in dimension of window and place
            clarificationText = textwrap.wrap("Please enter a valid " + invalidFields, width = 50, break_long_words = False, placeholder = '')
        else:
            clarificationText = textwrap.wrap("Ingredient name is already taken. Please enter a different name.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=validationPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=validationPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command=closeValidationPopup, text="  Got it  ",  fg="#273A36", activeforeground='white', font=("Arial", 25), highlightbackground='#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it#open window and pass execution to it
        validationPopupWindow.geometry("600x500+360+140")
        validationPopupWindow.configure(background = "#C6D8D9")
        validationPopupWindow.mainloop()
        
    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeValidationPopup():
        global validationPopupWindow
        validationPopupWindow.grab_release()
        validationPopupWindow.destroy()

    #creates all the widgets within a single row of quantity in stock entries and returns the frame
    def newQtyInStockRow():
       rowFrame = tk.Frame(master= window1, background = "#D8D7E8")
       #create label (title) for quantity in stock 
       qtyInStockLabel = tk.Label(master=rowFrame, fg = "#4F2C54", background = "#D8D7E8", text="Quantity in Stock", font=("Arial", 20))
       qtyInStockLabel.grid(row = 0, column = 0)
       #create entry for quantity in stock
       qtyInStockEntry = tk.Entry(rowFrame, width = 10)
       qtyInStockEntry.bind('<Button>', enterValue)
       qtyInStockEntry.grid(row=0, column = 1, padx = 10)
       #create label (title) for expiry date
       expiryDateLabel = tk.Label(master=rowFrame, fg = "#4F2C54", background = "#D8D7E8", text="Expiry Date", font=("Arial", 20))
       expiryDateLabel.grid(row = 0, column = 2, padx = (120,0))
       #create entry for expiry date with format placeholder
       expiryDateEntry = tk.Entry(rowFrame, width = 20, fg = '#D7D7D7')
       expiryDateEntry.bind('<Button>', enterValue)
       expiryDateEntry.insert(0, ' DD/MM/YYYY')
       expiryDateEntry.grid(row=0, column = 3, padx = 10)
       return rowFrame

    #triggered by the '+' button to add another row of entry fields for purchasable quantities
    def addPurchasableQtyRow():
       global extraRowFrame1
       global extraRowFrame2
       global extraRowFrame3
       global extraRowFrame4
       global qtyInStockRows
       global qtyEntries
       #determine positions of rows based on rows already displayed on page
       if extraRowFrame1 is None:
          if extraRowFrame4 != None:
             #move existing rows
             row3Frame.place(relx=.09, rely=.43)
             qtyInStockRows[0].place(relx=.25, rely=.47)
             qtyInStockRows[1].place(relx=.25, rely=.54)
             qtyInStockRows[2].place(relx=.25, rely=.61)
             extraRowFrame3.place(relx=.25, rely=.68)
             #create and place 1st extra row of purchasable quantities
             extraRowFrame1 = tk.Frame(master= window1, background = "#D8D7E8")
             for i in range(0,6):
                qtyEntries.append(tk.Entry(extraRowFrame1, width = 10, fg = '#D7D7D7'))
                qtyEntries[len(qtyEntries)-1].bind("<Button>", enterValue)
                qtyEntries[len(qtyEntries)-1].insert(0, ' Qty')
                qtyEntries[len(qtyEntries)-1].grid(row=0, column = [i+2], padx = 10)
             extraRowFrame1.place(relx=.245, rely=.37)
          elif extraRowFrame3 != None:
             #move existing rows
             row3Frame.place(relx=.09, rely=.45)
             qtyInStockRows[0].place(relx=.25, rely=.53)
             qtyInStockRows[1].place(relx=.25, rely=.6)
             qtyInStockRows[2].place(relx=.25, rely=.67)
             extraRowFrame3.place(relx=.25, rely=.74)
             #create and place 1st extra row of purchasable quantities
             extraRowFrame1 = tk.Frame(master= window1, background = "#D8D7E8")
             for i in range(0,6):
                qtyEntries.append(tk.Entry(extraRowFrame1, width = 10, fg = '#D7D7D7'))
                qtyEntries[len(qtyEntries)-1].bind("<Button>", enterValue)
                qtyEntries[len(qtyEntries)-1].insert(0, ' Qty')
                qtyEntries[len(qtyEntries)-1].grid(row=0, column = [i+2], padx = 10)
             extraRowFrame1.place(relx=.245, rely=.37)
          else:
             #move existing rows
             row3Frame.place(relx=.09, rely=.5)
             qtyInStockRows[0].place(relx=.25, rely=.58)
             qtyInStockRows[1].place(relx=.25, rely=.66)
             qtyInStockRows[2].place(relx=.25, rely=.74)
             #create and place 1st extra row of purchasable quantities
             extraRowFrame1 = tk.Frame(master= window1, background = "#D8D7E8")
             for i in range(0,6):
                qtyEntries.append(tk.Entry(extraRowFrame1, width = 10, fg = '#D7D7D7'))
                qtyEntries[len(qtyEntries)-1].bind("<Button>", enterValue)
                qtyEntries[len(qtyEntries)-1].insert(0, ' Qty')
                qtyEntries[len(qtyEntries)-1].grid(row=0, column = [i+2], padx = 10)
             extraRowFrame1.place(relx=.245, rely=.37)
       elif extraRowFrame2 is None:
          if extraRowFrame4 != None:
             extraRowFrame2 = tk.Frame(master= window1, background = "#D8D7E8")
             #create and place 2nd extra row of purchasable quantities
             for i in range(0,6):
                qtyEntries.append(tk.Entry(extraRowFrame2, width = 10, fg = '#D7D7D7'))
                qtyEntries[len(qtyEntries)-1].bind("<Button>", enterValue)
                qtyEntries[len(qtyEntries)-1].insert(0, ' Qty')
                qtyEntries[len(qtyEntries)-1].grid(row=0, column = [i+2], padx = 10)
             #move existing rows
             extraRowFrame1.place(relx=.245, rely=.38)
             extraRowFrame2.place(relx=.245, rely=.46)
             extraRowFrame4.place(relx=.25, rely=.75)
             row3Frame.place(relx=.09, rely=.5)
             qtyInStockRows[0].place(relx=.25, rely=.55)
             qtyInStockRows[1].place(relx=.25, rely=.6)
             qtyInStockRows[2].place(relx=.25, rely=.65)
             extraRowFrame3.place(relx=.25, rely=.7)
          elif extraRowFrame3 != None:
              #move existing rows
             row3Frame.place(relx=.09, rely=.49)
             qtyInStockRows[0].place(relx=.25, rely=.53)
             qtyInStockRows[1].place(relx=.25, rely=.59)
             qtyInStockRows[2].place(relx=.25, rely=.65)
             extraRowFrame3.place(relx=.25, rely=.71)
             #create and place 2nd extra row of purchasable quantities
             extraRowFrame2 = tk.Frame(master= window1, background = "#D8D7E8")
             for i in range(0,6):
                qtyEntries.append(tk.Entry(extraRowFrame2, width = 10, fg = '#D7D7D7'))
                qtyEntries[len(qtyEntries)-1].bind("<Button>", enterValue)
                qtyEntries[len(qtyEntries)-1].insert(0, ' Qty')
                qtyEntries[len(qtyEntries)-1].grid(row=0, column = [i+2], padx = 10)
             extraRowFrame2.place(relx=.245, rely=.41)
          else:
             #move existing rows
             row3Frame.place(relx=.09, rely=.55)
             qtyInStockRows[0].place(relx=.25, rely=.59)
             qtyInStockRows[1].place(relx=.25, rely=.65)
             qtyInStockRows[2].place(relx=.25, rely=.71)
             #create and place 2nd extra row of purchasable quantities
             extraRowFrame2 = tk.Frame(master= window1, background = "#D8D7E8")
             for i in range(0,6):
                qtyEntries.append(tk.Entry(extraRowFrame2, width = 10, fg = '#D7D7D7'))
                qtyEntries[len(qtyEntries)-1].bind("<Button>", enterValue)
                qtyEntries[len(qtyEntries)-1].insert(0, ' Qty')
                qtyEntries[len(qtyEntries)-1].grid(row=0, column = [i+2], padx = 10)
             extraRowFrame2.place(relx=.245, rely=.45)
       else:
          #max rows added
          pass

   
    def addQtyInStockRow():
       global extraRowFrame1
       global extraRowFrame2
       global extraRowFrame3
       global extraRowFrame4
       global qtyInStockRows
       global addQtyInStockButton
       #determine positions of rows based on rows already displayed on page
       if extraRowFrame1 is None:
          if extraRowFrame3 is None:
             #create and place 1st extra row of quantities in stock
             extraRowFrame3 = newQtyInStockRow()
             #destroy and replace '+' button in bottom row
             addQtyInStockButton.destroy()
             addQtyInStockButton = tk.Button(master = extraRowFrame3, command = addQtyInStockRow, text = '+', width = 4, height = 2)
             addQtyInStockButton.grid(column = 4, row = 0)
             extraRowFrame3.place(relx=.25, rely=.68+.079)
          elif extraRowFrame4 is None:
             #create and place 2nd extra row of quantities in stock
             extraRowFrame4 =  newQtyInStockRow()
             #move existing rows
             row3Frame.place(relx=.09, rely=.39)
             qtyInStockRows[0].place(relx=.25, rely=.47)
             qtyInStockRows[1].place(relx=.25, rely=.54)
             qtyInStockRows[2].place(relx=.25, rely=.61)
             extraRowFrame3.place(relx=.25, rely=.68)
             #destroy and replace '+' button in bottom row
             addQtyInStockButton.destroy()
             addQtyInStockButton = tk.Button(master = extraRowFrame4, command = addQtyInStockRow, text = '+', width = 4, height = 2)
             addQtyInStockButton.grid(column = 4, row = 0)
             extraRowFrame4.place(relx=.25, rely=.68+.079)
          else:
              pass
             #max rows added
       elif extraRowFrame2 is None:
          if extraRowFrame3 is None:
             #create and place 1st extra row of quantities in stock
             extraRowFrame3 =  newQtyInStockRow()
             extraRowFrame3.place(relx=.25, rely=.68+.079)
             row3Frame.place(relx=.09, rely=.47)
             #move existing rows
             qtyInStockRows[0].place(relx=.25, rely=.54)
             qtyInStockRows[1].place(relx=.25, rely=.61)
             qtyInStockRows[2].place(relx=.25, rely=.68)
             #destroy and replace '+' button in bottom row
             addQtyInStockButton.destroy()
             addQtyInStockButton = tk.Button(master = extraRowFrame3, command = addQtyInStockRow, text = '+', width = 4, height = 2)
             addQtyInStockButton.grid(column = 4, row = 0)
          elif extraRowFrame4 is None:
             #create and place 2nd extra row of quantities in stock
             extraRowFrame4 =  newQtyInStockRow()
             extraRowFrame4.place(relx=.25, rely=.76)
             #move existing rows
             row3Frame.place(relx=.09, rely=.45)
             qtyInStockRows[0].place(relx=.25, rely=.52)
             qtyInStockRows[1].place(relx=.25, rely=.58)
             qtyInStockRows[2].place(relx=.25, rely=.64)
             extraRowFrame3.place(relx=.25, rely=.7)
             #destroy and replace '+' button in bottom row
             addQtyInStockButton.destroy()
             addQtyInStockButton = tk.Button(master = extraRowFrame4, command = addQtyInStockRow, text = '+', width = 4, height = 2)
             addQtyInStockButton.grid(column = 4, row = 0)
          else:
              pass
             #max rows added
       else:
          if extraRowFrame3 is None:
             #create and place 1st extra row of quantities in stock
             extraRowFrame3 =  newQtyInStockRow()
             extraRowFrame3.place(relx=.25, rely=.68+.079)
             #move existing rows
             extraRowFrame1.place(relx=.245, rely=.37)
             extraRowFrame2.place(relx=.245, rely=.44)
             row3Frame.place(relx=.09, rely=.50)
             qtyInStockRows[0].place(relx=.25, rely=.56)
             qtyInStockRows[1].place(relx=.25, rely=.63)
             qtyInStockRows[2].place(relx=.25, rely=.7)
             #destroy and replace '+' button in bottom row
             addQtyInStockButton.destroy()
             addQtyInStockButton = tk.Button(master = extraRowFrame3, command = addQtyInStockRow, text = '+', width = 4, height = 2)
             addQtyInStockButton.grid(column = 4, row = 0)
          elif extraRowFrame4 is None:
             #create and place 2nd extra row of quantities in stock
             extraRowFrame4 =  newQtyInStockRow()
             extraRowFrame4.place(relx=.25, rely=.75)
             #move existing rows
             extraRowFrame2.place(relx=.245, rely=.42)
             row3Frame.place(relx=.09, rely=.49)
             qtyInStockRows[0].place(relx=.25, rely=.55)
             qtyInStockRows[1].place(relx=.25, rely=.6)
             qtyInStockRows[2].place(relx=.25, rely=.65)
             extraRowFrame3.place(relx=.25, rely=.7)
             #destroy and replace '+' button in bottom row
             addQtyInStockButton.destroy()
             addQtyInStockButton = tk.Button(master = extraRowFrame4, command = addQtyInStockRow, text = '+', width = 4, height = 2)
             addQtyInStockButton.grid(column = 4, row = 0)
          else:
              pass
             #max rows added

    #triggered whenever a new widget is clicked
    def enterValue(event):
        try:
           #deletes format placeholder in clicked widget so user can enter text
           if event.widget.get() == ' Qty' or event.widget.get() == ' DD/MM/YYYY' or event.widget.get() == '' or event.widget.get().isspace() == True:
             event.widget.delete(0, tk.END)
             event.widget.configure(fg = 'black')
        except:
           pass
        global qtyEntries
        for entry in qtyEntries:
           #re-enter format placeholder in any other empty purchasable quantity entry widgets
           if entry != event.widget and entry.get() == '':
              entry.configure(fg = '#D7D7D7')
              entry.insert(0, ' Qty')
        for frame in qtyInStockRows:
           for frameItem in frame.children.items():
              #re-enter format placeholder in any other empty expiry date entry widgets
              if '!entry2' in frameItem[0] and frameItem[1].get() == '' and frameItem[1] != event.widget:
                 frameItem[1].configure(fg = '#D7D7D7')
                 frameItem[1].insert(0, ' DD/MM/YYYY')


    #triggered when ingredient selected to show other entry widgets as needed
    def showOtherFields(event):
       #fetch ingredient selected
       ingredient = combo.get()
       combo.bind('<Button>', enterValue)
       #show new name entry widget if new ingredient selected       
       if ingredient == ' + New Ingredient':
            newIngredientNameLabel.place(relx = .44, rely = .205)
            newIngredientNameEntry.place(relx = .57, rely = .205)
       else:
           #hide new name entry widget  
           newIngredientNameLabel.place_forget()
           newIngredientNameEntry.place_forget()

       #create and place ingredient unit label, entry, and clarify button widgets on page
       global unitEntry
       unitLabel = tk.Label(master=window1, fg = "#4F2C54", background = "#D8D7E8", text="Unit", font=("Arial", 20))
       unitLabel.place(relx = .79, rely = .2)
       unitEntry = tk.Entry(window1, width = 10)
       unitEntry.bind('<Button>', enterValue)
       unitEntry.place(relx = .83, rely = .2)
       unitEntry.delete(0, tk.END)
       unitClarifyButton = tk.Button(master=window1, command = unitClarifyPopup, width = 4, height = 2, text = '?')
       unitClarifyButton.place(relx = .91, rely = .2)
       unitClarifyButton.bind('<Button>', enterValue)
   
       global extraRowFrame1
       global extraRowFrame2
       global extraRowFrame3
       global extraRowFrame4
       global row3Frame
       global qtyInStockRows

       #destroy any displayed extra rows from any previously selected ingredient
       try:
          extraRowFrame1.destroy()
          extraRowFrame1 = None
       except:
          pass
       try:
          extraRowFrame2.destroy()
          extraRowFrame2 = None
       except:
          pass
       try:
          extraRowFrame3.destroy()
          extraRowFrame3 = None
       except:
          pass
       try:
          extraRowFrame4.destroy()
          extraRowFrame4 = None
       except:
          pass
       try:
          row3Frame.destroy()
          row3Frame = None
       except:
          pass
       try:
          qtyInStockRows[0].destroy()
       except:
          pass
       try:
          qtyInStockRows[1].destroy()
       except:
          pass
       try:
          qtyInStockRows[2].destroy()
       except:
          pass
       qtyInStockRows = []

       #create frame for second row 
       row2Frame = tk.Frame(master= window1, background = "#D8D7E8")
       #create clarification button
       purchasableQtyClarifyButton = tk.Button(master=row2Frame, text = '?', width = 4, command = purchasableClarifyPopup, height = 2)
       purchasableQtyClarifyButton.grid(column = 0, row = 0, padx = 20)
       purchasableQtyClarifyButton.bind('<Button>', enterValue)
       #create label (title) for purchasable quantity entry widgets
       purchasableQtyLabel = tk.Label(master=row2Frame, fg = "#4F2C54", background = "#D8D7E8", text="Purchasable Quantities", font=("Arial", 20))
       purchasableQtyLabel.grid(row = 0, column = 1)
       global qtyEntries
       qtyEntries = []
       #create a row in frame with 6 quantity entry widgets 
       for i in range(0,6):
          qtyEntries.append(tk.Entry(row2Frame, width = 10, fg = '#D7D7D7'))
          qtyEntries[i].insert(0, ' Qty')
          qtyEntries[i].bind("<Button>", enterValue)
          qtyEntries[i].grid(row=0, column = [i+2], padx = 10)

       #create '+' button in second row and place
       addPuchasableQtyButton = tk.Button(master=row2Frame, command = addPurchasableQtyRow, text = '+', width = 4, height = 2)
       addPuchasableQtyButton.grid(column = 8, row = 0, padx = 30)
       addPuchasableQtyButton.bind('<Button>', enterValue)
       row2Frame.place(relx=.04, rely=.3)

       #create and display third row with shelf life label and entry widgets
       global shelfLifeEntry
       row3Frame = tk.Frame(master= window1, background = "#D8D7E8")
       shelfLifeLabel = tk.Label(master=row3Frame, fg = "#4F2C54", background = "#D8D7E8", text="Shelf Life (days)", font=("Arial", 20))
       shelfLifeLabel.grid(row = 0, column = 0)
       shelfLifeEntry = tk.Entry(row3Frame, width = 10)
       shelfLifeEntry.grid(row=0, column = 1, padx = 10)
       shelfLifeEntry.bind('<Button>', enterValue)
       shelfLifeEntry.delete(0, tk.END)
       row3Frame.place(relx=.09, rely=.41)

       #create 3 rows of stock quantity-expiry date pairs and place under each other
       y = 0.52
       qtyInStockRows = []
       for i in range (0,3):
          rowFrame = newQtyInStockRow()
          rowFrame.place(relx=.25, rely=y)
          qtyInStockRows.append(rowFrame)
          y=y+0.079

       #create '+' button in bottom stock row and place  
       global addQtyInStockButton
       addQtyInStockButton = tk.Button(master = qtyInStockRows[2], command = addQtyInStockRow, text = '+', width = 4, height = 2)
       addQtyInStockButton.grid(column = 4, row = 0)

       #fetch all purchasable quantities for selected ingredient from database
       mycursor.execute("SELECT PurchasableQuantity FROM tblPuchasableQuantity, tblBaseIngredient WHERE IngredientName = '" + ingredient + "' AND tblBaseIngredient.IngredientID = tblPuchasableQuantity.IngredientID")
       purchasableQtys = mycursor.fetchall()
       #add extra quantity rows if needed to fit all stored quantities
       if len(purchasableQtys)>6:
            addPurchasableQtyRow()
       if len(purchasableQtys)>12:
            addPurchasableQtyRow()
       if len(purchasableQtys)>18:
            addPurchasableQtyRow()
       count = 0
       #insert quantities into widgets 
       for item in qtyEntries:
            try:
                #insert quantity into ingredient widget
                item.delete(0, tk.END)
                item.configure(fg = 'black')
                quantity = purchasableQtys[count][0]
                item.insert(0, quantity)
                count = count + 1
            except:
                #no more stored ingredients to insert so add format placeholder
                item.delete(0, tk.END)
                item.configure(fg = '#D7D7D7')
                item.insert(0, ' Qty')

       #fetch stored shelf life and quantity unit from database
       mycursor.execute("SELECT ShelfLife, QuantityUnit FROM tblBaseIngredient WHERE IngredientName = '" + ingredient + "'")
       records = mycursor.fetchall()[0]
       #insert stored shelf life into widget
       try:
           shelfLifeEntry.insert(0, records[0])
       except:
           pass
       #insert stored unit into widget
       try:
           unitEntry.insert(0, records[1])
       except:
           pass

       #fetch stored quantities in stock and expiry dates from database
       mycursor.execute("SELECT Quantity, ExpiryDate FROM tblItemsInStock, tblBaseIngredient WHERE IngredientName = '" + ingredient + "' AND tblBaseIngredient.IngredientID = tblItemsInStock.IngredientID")
       records = mycursor.fetchall()
       #add extra quantity rows if needed to fit all stored quantities
       if len(records)>3:
            addQtyInStockRow()
            extra3Flag = True
       if len(records)>4:
            addQtyInStockRow()
            extra4Flag = True
       if len(records)>5:
            addQtyInStockRow()
       count = 0
       #insert quantities and expiry dates into widgets 
       for row in qtyInStockRows:
            for item in row.children.items():
                try:
                    if '!entry2' in item[0]:
                        #insert expiry date into entry widget
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = 'black')
                        item[1].insert(0, (records[count][1]).strftime("%d/%m/%Y"))
                        count = count + 1
                    elif '!entry' in item[0]:
                        #insert quantity in stock into entry widget
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = 'black')
                        item[1].insert(0, records[count][0])
                except:
                    if '!entry2' in item[0]:
                        #no more stored dates to insert so add format placeholder
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = '#D7D7D7')
                        item[1].insert(0, ' DD/MM/YYYY')  
                    elif '!entry' in item[0]:
                        #no more stored quantities to insert so add format placeholder
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = '#D7D7D7')
       if extra3Flag == True:
           #insert quantities and expiry dates into extra row 3 widgets (as above)
           for item in extraRowFrame3.children.items():
                try:
                    if '!entry2' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = 'black')
                        item[1].insert(0, (records[count][1]).strftime("%d/%m/%Y"))
                        count = count + 1
                    elif '!entry' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = 'black')
                        item[1].insert(0, records[count][0])
                except:
                    if '!entry2' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = '#D7D7D7')
                        item[1].insert(0, ' DD/MM/YYYY')  
                    elif '!entry' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = '#D7D7D7')
       if extra4Flag == True:
           #insert quantities and expiry dates into extra row 4 widgets (as above)
           for item in extraRowFrame4.children.items():
                try:
                    if '!entry2' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = 'black')
                        item[1].insert(0, (records[count][1]).strftime("%d/%m/%Y"))
                        count = count + 1
                    elif '!entry' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = 'black')
                        item[1].insert(0, records[count][0])
                except:
                    if '!entry2' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = '#D7D7D7')
                        item[1].insert(0, ' DD/MM/YYYY')  
                    elif '!entry' in item[0]:
                        item[1].delete(0, tk.END)
                        item[1].configure(fg = '#D7D7D7')

    #destroy any existing rows from previous ingredient
    global qtyInStockRows
    qtyInStockRows = []
    global qtyEntries
    qtyEntries = []
    global extraRowFrame1
    extraRowFrame1 = None
    global extraRowFrame2
    extraRowFrame2 = None
    global extraRowFrame3
    extraRowFrame3 = None
    global extraRowFrame4
    extraRowFrame4 = None
    global row3Frame
    row3Frame = None

    #create and display ingredient name label and entry widgets 
    ingredientNameLabel = tk.Label(master=window1, fg = "#4F2C54", background = "#D8D7E8", text="Ingredient Name", font=("Arial", 20))
    ingredientNameLabel.place(relx = .09, rely = .2)
    combo = ttk.Combobox(window1, textvariable=tk.StringVar(), width = 30, values=[' + New Ingredient'], style = "TCombobox")
    global newIngredientFlag
    #check if new ingredient is immediately being entered when called from another page with '+ New Ingredient'
    if newIngredientFlag == True:
        combo.insert(0, ' + New Ingredient')
        #trigger showOtherFields function to show new fields as soon as new window opened
        combo.bind('<Map>', showOtherFields)
    combo.place(relx = .2, rely = .205)
    #create search button and link to combobox widget
    searchButton = tk.Button(window1, text='Search')
    searchButton.place(relx = .40, rely = .205)
    searchButton.bind('<Button>', enterValue)
    searchButton.bind('<Button>', searchForIngredient)
    global pairing
    pairing[searchButton] = combo
    combo.bind('<<ComboboxSelected>>', showOtherFields)
    #create widgets for new ingredient name but don't display immediately
    newIngredientNameLabel = tk.Label(master=window1, fg = "#4F2C54", background = "#D8D7E8", text="New Ingredient Name", font=("Arial", 18))
    newIngredientNameEntry = tk.Entry(window1, width = 30)
            
    #create widgets for bottom row (buttons) of page
    row7Frame = tk.Frame(master=window1)
    row7Frame.configure(pady=50, background = "#D8D7E8")
    #button to validate and save user's entries for recipe when all fields entered
    confirmButtonBorder = tk.Frame(row7Frame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, text="Confirm",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), command = validate, highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.grid(column=0, row = 0)
    #button to cancel recipe entry
    cancelButtonBorder = tk.Frame(row7Frame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    cancelButton = tk.Button(master=cancelButtonBorder, text="Cancel", command = closeModule, activeforeground='white', fg = "#273A36",   font = ("Arial", 25), highlightbackground = '#C6D8D9')
    cancelButton.pack()
    cancelButtonBorder.grid(column=1, row = 0, padx = 40)
    row7Frame.place(relx=.40, rely=.77)

    #if page should be opening in new window, open window on top of previous one and pass execution to it
    if newWindowFlag == True:
        window1.geometry("1400x800+110+20")
        window1.configure(background = "#D8D7E8")
        window1.mainloop()

#create and display window with 'Add Working Hours' page, triggered from 'Add Order' page
def addWorkingHours():
    schWindow = tk.Toplevel()
    schWindow.grab_set()
    global added
    added = 0

    #fetch new order date and name from 'Add Order' page called from
    global orderDateEntry
    orderDate = orderDateEntry.get()
    global tempSlots
    global orderNameEntry
    orderName = orderNameEntry.get()

    #triggered when slots all confirmed or cancelled to destroy window and pass back execution
    def closeModule():
        global specificDateError
        specificDateError = True
        global tempSlots
        prepFlag = False
        decorFlag = False
        invalidFields = []
        for slot in tempSlots:
            if slot[4] == 'PREP':
                prepFlag = True
            elif slot[4] == 'DECOR':
                decorFlag = True
        if decorFlag == False and prepFlag == False:
            invalidFields = ['Please add at least one prep and one decor slot']
        elif decorFlag == False:
            invalidFields = ['Please add at least one decor slot']
        elif prepFlag == False:
            invalidFields = ['Please add at least one prep slot']

            
        if invalidFields != []:
            validationPopup(invalidFields)
        else:
            if prepSlotSTimeEntry.get().isspace != True and prepSlotSTimeEntry.get() != '' and prepSlotSTimeEntry.get() != ' hh:mm':
                #invalid if any text left in either entry widget
                invalidFields.append('entered prep slot (values left in entry boxes)')
            elif prepSlotETimeEntry.get().isspace != True and prepSlotETimeEntry.get() != '' and prepSlotETimeEntry.get() != ' hh:mm':
                invalidFields.append('entered prep slot (values left in entry boxes)')
            elif prepSlotDateEntry.get().isspace != True and prepSlotDateEntry.get() != '' and prepSlotDateEntry.get() != ' DD/MM/YYYY':
                invalidFields.append('entered prep slot (values left in entry boxes)')
            if decorSlotSTimeEntry.get().isspace != True and decorSlotSTimeEntry.get() != '' and decorSlotSTimeEntry.get() != ' hh:mm':
                #invalid if any text left in either entry widget
                invalidFields.append('entered decor slot (values left in entry boxes)')
            elif decorSlotETimeEntry.get().isspace != True and decorSlotETimeEntry.get() != '' and decorSlotETimeEntry.get() != ' hh:mm':
                invalidFields.append('entered decor slot (values left in entry boxes)')
            elif decorSlotDateEntry.get().isspace != True and decorSlotDateEntry.get() != '' and decorSlotDateEntry.get() != ' DD/MM/YYYY':
                invalidFields.append('entered decor slot (values left in entry boxes)')
            specificDateError = False
            if invalidFields != []:
                validationPopup(invalidFields)
            else:
                schWindow.grab_release()
                schWindow.destroy()
        
    #triggered when slots from session cancelled, forget slots and destroy window
    def closeModuleCancel():
        for i in range(0, added):
            tempSlots.pop()
        schWindow.grab_release()
        schWindow.destroy()
        

    #triggered whenever a new widget is clicked
    def enterValue(event):
        if event.widget.get() == ' DD/MM/YYYY' or event.widget.get() == ' hh:mm':
            #deletes format placeholder in clicked widget so user can enter text
            event.widget.delete(0, tk.END)
            event.widget.configure(fg = 'black')
        if (prepSlotDateEntry.get() == '' or prepSlotDateEntry.get().isspace == True) and event.widget != prepSlotDateEntry:
            #re-enter format placeholder in entry widget if not clicked and not filled
            prepSlotDateEntry.delete(0, tk.END)
            prepSlotDateEntry.configure(fg = '#D7D7D7')
            prepSlotDateEntry.insert(0, ' DD/MM/YYYY')
        if (decorSlotDateEntry.get() == '' or decorSlotDateEntry.get().isspace == True) and event.widget != decorSlotDateEntry:
            #re-enter format placeholder in entry widget if not clicked and not filled
            decorSlotDateEntry.delete(0, tk.END)
            decorSlotDateEntry.configure(fg = '#D7D7D7')
            decorSlotDateEntry.insert(0, ' DD/MM/YYYY')
        for frame in schWindow.winfo_children():
            for widget in frame.winfo_children():
                #re-enter format placeholder in other entry widgets (slot times) 
                if widget != decorSlotDateEntry and widget != prepSlotDateEntry and widget.winfo_class() == 'Entry' and (widget.get() == '' or widget.get().isspace == True) and widget != event.widget:
                    widget.delete(0, tk.END)
                    widget.configure(fg = '#D7D7D7')
                    widget.insert(0, ' hh:mm')



    def prepClear():
        #clear PREP entry widgets and re-enter format placeholders
        prepSlotDateEntry.delete(0, tk.END)
        prepSlotDateEntry.configure(fg = '#D7D7D7')
        prepSlotDateEntry.insert(0, ' DD/MM/YYYY')
        prepSlotSTimeEntry.delete(0, tk.END)
        prepSlotSTimeEntry.configure(fg = '#D7D7D7')
        prepSlotSTimeEntry.insert(0, ' hh:mm')
        prepSlotETimeEntry.delete(0, tk.END)
        prepSlotETimeEntry.configure(fg = '#D7D7D7')
        prepSlotETimeEntry.insert(0, ' hh:mm')

        
    #triggered when each PREP slot is confirmed
    def validatePrepSlot():
        #call validation function with correct widgets
        validateSlot(prepSlotDateEntry, prepSlotSTimeEntry, prepSlotETimeEntry, 'PREP')
        prepClear()


    def decorClear():
        #clear DECOR entry widgets and re-enter format placeholders
        decorSlotDateEntry.delete(0, tk.END)
        decorSlotDateEntry.configure(fg = '#D7D7D7')
        decorSlotDateEntry.insert(0, ' DD/MM/YYYY')
        decorSlotSTimeEntry.delete(0, tk.END)
        decorSlotSTimeEntry.configure(fg = '#D7D7D7')
        decorSlotSTimeEntry.insert(0, ' hh:mm')
        decorSlotETimeEntry.delete(0, tk.END)
        decorSlotETimeEntry.configure(fg = '#D7D7D7')
        decorSlotETimeEntry.insert(0, ' hh:mm')

    #triggered when each DECOR slot is confirmed
    def validateDecorSlot():
        #call validation function with correct widgets
        validateSlot(decorSlotDateEntry, decorSlotSTimeEntry, decorSlotETimeEntry, 'DECOR')
        #clear DECOR entry widgets and re-enter format placeholders
        decorClear()


    #checks entered slot, adds to tempSlot array and graphical schedule if valid, displays message to user if not
    def validateSlot(dateEntry, startEntry, endEntry, slotType):
        invalidFields = []
        global date
        global tempSlots
        #fetch slot date, start time, and end time from passed in widgets on page
        date = dateEntry.get()
        startTime = startEntry.get()
        endTime = endEntry.get()

        #check date field
        if date == '' or date.isspace() == True or date == ' DD/MM/YYYY':
            #invalid if no date entered
            invalidFields.append('Slot Date')
        else:
            try:
                date = datetime.strptime(date, "%d/%m/%Y")
            except ValueError:
                #invalid if date not a valid date in correct format 
                invalidFields.append('Slot Date')
        if startTime == '' or startTime.isspace() == True or startTime == ' hh:mm':
            #invalid if no start time entered
            invalidFields.append('Slot Start Time')
        else:
            try:
                datetime.strptime(startTime, "%H:%M")
            except ValueError:
                #invalid if start time not a valid time in correct format 
                invalidFields.append('Slot Start Time')

        if endTime == '' or endTime.isspace() == True or endTime == ' hh:mm':
            #invalid if no end time entered
            invalidFields.append('Slot End Time')
        else:
            try:
                datetime.strptime(endTime, "%H:%M")
            except ValueError:
                #invalid if end time not a valid time in correct format 
                invalidFields.append('Slot End Time')
                
        global specificDateError
        specificDateError = False
        
        #display error message popup if any invalid fields were identified  
        if invalidFields != []:
            validationPopup(invalidFields)
        else:
            #check if date is >= today's date
            if date.date() < today:
                specificDateError = True
                invalidFields.append('Slot date is in the past')
            #check if date is in week during currently displayed
            global currentWeekShown
            currentWeekShown = datetime.strptime(currentWeekShown, "%Y-%m-%d")
            weekEnd = currentWeekShown + timedelta(days=6)
            if date.date() < currentWeekShown.date() or date.date() > weekEnd.date():
                specificDateError = True
                invalidFields.append('Slot date is not within displayed week')
            currentWeekShown = str(currentWeekShown)[:10]
            #check if start time is before end time            
            startTime = datetime.strptime(str(date)[:11] + startTime, "%Y-%m-%d %H:%M")
            endTime = datetime.strptime(str(date)[:11] + endTime, "%Y-%m-%d %H:%M")
            if startTime >= endTime:
                specificDateError = True
                invalidFields.append('Slot start time is after end time')
            #check if times can be shown on schedule 
            if startTime.time() < (datetime.strptime('06:00', "%H:%M")).time() or endTime.time() > (datetime.strptime('21:00', "%H:%M")).time() :
                specificDateError = True
                invalidFields.append('Slot cannot be displayed on schedule (Too late/early)')                
            #display error message popup if any specific invalid dates/times were identified above  
            if invalidFields != []:
                validationPopup(invalidFields)
            else:
                global currentSlot
                currentSlot = (orderName, date, startTime, endTime, slotType)
                #slot valid - check if any clashes
                for tempSlot in tempSlots:
                    if date == tempSlot[1]:
                        if (startTime >= tempSlot[2] and startTime <= tempSlot[3]) or (endTime >= tempSlot[2] and endTime <= tempSlot[3]):
                            #alert user the slot clashes with another temp slot
                            clashPopup()
                #alert user if the slot clashes with another STORED slot from database
                mycursor.execute("SELECT OrderName, Date, StartTime, EndTime FROM tblWorkingDateSlot, tblCustomerOrder WHERE tblWorkingDateSlot.OrderID = tblCustomerOrder.OrderID")
                allSlots = mycursor.fetchall()
                for storedSlot in allSlots:
                    if date.date() == storedSlot[1]:
                        if (startTime.time() >= (datetime.min + storedSlot[2]).time() and startTime.time() <= (datetime.min + storedSlot[3]).time()) or (endTime.time() >= (datetime.min + storedSlot[2]).time() and endTime.time() <= (datetime.min + storedSlot[3]).time()): 
                            clashPopup()
                global added
                added += 1
                tempSlots.append((orderName, date, startTime, endTime, slotType))
                #delete and re-create graphical schedule with new slot and display on page
                global schedule
                del schedule
                schedule = create_graphical_schedule(currentWeekShown, tempSlots, schWindow)
                schedule.place(relx = .5, rely = .25)

        
    #creates and displays popup window to alert user of any invalid field entries on page
    def validationPopup(invalidFields):
        #format message text and create window
        invalidFields = ', '.join(invalidFields)
        global validationPopupWindow
        validationPopupWindow = tk.Toplevel()
        validationPopupWindow.grab_set()

        #change message depending on invalid fields 
        global specificDateError
        if specificDateError == True:
            #format text so it fits in dimension of window and place
            clarificationText = textwrap.wrap("Error with slot: " + invalidFields, width = 50, break_long_words = False, placeholder = '')
        else:
            clarificationText = textwrap.wrap("Please enter a valid " + invalidFields, width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=validationPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read warning message and place
        buttonsFrame = tk.Frame(master=validationPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeValidationPopup, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        validationPopupWindow.geometry("600x500+360+140")
        validationPopupWindow.configure(background = "#C6D8D9")
        validationPopupWindow.mainloop()
        
    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeValidationPopup():
        global validationPopupWindow
        validationPopupWindow.grab_release()
        validationPopupWindow.destroy()

    #creates and displays popup window to alert user of a slot clash
    def clashPopup():
        global clashPopupWindow
        clashPopupWindow = tk.Toplevel()
        clashPopupWindow.grab_set()
        #format text so it fits in dimension of window and place
        clarificationText = textwrap.wrap("Warning: New slot may clash with existing slot. It will be added, but you can delete this slot through the 'Delete Order' page if needed.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=clashPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read warning message and place
        buttonsFrame = tk.Frame(master=clashPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeClashPopup, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        clashPopupWindow.geometry("600x500+360+140")
        clashPopupWindow.configure(background = "#C6D8D9")
        clashPopupWindow.mainloop()
        
    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeClashPopup():
        global clashPopupWindow
        global tempSlots
        global added
        global currentSlot
        global currentWeekShown
        #clear widgets
        if currentSlot[4] == 'DECOR':
            decorClear()
        else:
            prepClear()
        #add slot to tempSlot array for this order
        added += 1
        tempSlots.append(currentSlot)
        currentSlot = ('')
        #delete and re-create graphical schedule with new slot and display on page
        global schedule
        del schedule
        schedule = create_graphical_schedule(currentWeekShown, tempSlots, schWindow)
        schedule.place(relx = .5, rely = .25)
        clashPopupWindow.grab_release()
        clashPopupWindow.destroy()

    #display explanation popup window for entering slot dates when user clicks '?' button
    def slotDateClarifyPopup():
        global dateClarifyPopupWindow
        dateClarifyPopupWindow = tk.Toplevel()
        dateClarifyPopupWindow.grab_set()

        #format text so it fits in dimension of window and place
        clarificationText = textwrap.wrap("Every slot must meet the following conditions: Not before today's date, and within the week displayed on the schedule on the right of the window (you can change the week displayed by pressing the arrow buttons). Dates must be in the format DD/MM/YYYY, and be an existing date in the calendar (eg. not 30th February). Times must be in the format hh:mm in 24 hour time (eg. 13:30). The start time of the slot must be before the end time of the slot.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=dateClarifyPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=dateClarifyPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeDateClarify, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it
        dateClarifyPopupWindow.geometry("600x500+360+140")
        dateClarifyPopupWindow.configure(background = "#C6D8D9")
        dateClarifyPopupWindow.mainloop()

    #triggered when button is pressed, to close popup window and pass back execution
    def closeDateClarify():
        global dateClarifyPopupWindow
        dateClarifyPopupWindow.grab_release()
        dateClarifyPopupWindow.destroy()
    
    #create and display title for add working hours window
    row1Frame = tk.Frame(master= schWindow, background = "#D8D7E8")
    scheduleLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="Schedule Working Hours", font=("Courier", 50))
    scheduleLabel.pack()
    row1Frame.place(relx = .5, rely = .07, anchor = 'c')

    #create and display subtitle for PREP working slots
    title1Frame = tk.Frame(master= schWindow, background = "#D8D7E8")
    title1Label = tk.Label(master=title1Frame, fg = "#4F2C54", background = "#D8D7E8", text="Prep Working Hours", font=("Arial", 20,'underline'))
    title1Label.pack()
    title1Frame.place(relx = .13, rely = .2, anchor = 'c')

    #create and display widgets for slot DATE
    prepSlotDateFrame= tk.Frame(master= schWindow, background = "#D8D7E8")
    dateClarifyButton = tk.Button(master=prepSlotDateFrame, text = '?', command = slotDateClarifyPopup, width = 4, height = 2)
    dateClarifyButton.grid(row=0, column = 0, padx = (0,20))
    prepSlotDateLabel = tk.Label(master=prepSlotDateFrame, fg = "#4F2C54", background = "#D8D7E8", text="Slot Date", font=("Arial", 20))
    prepSlotDateLabel.grid(row = 0, column = 1)
    prepSlotDateEntry = tk.Entry(prepSlotDateFrame, width = 20, fg = '#D7D7D7')
    prepSlotDateEntry.bind('<Button>', enterValue)
    prepSlotDateEntry.insert(0, ' DD/MM/YYYY')
    prepSlotDateEntry.grid(row=0, column = 2, padx = (40, 0))
    prepSlotDateFrame.place(relx = .02, rely = .25)

    #create and display widgets for slot START TIME
    prepSlotSTimeFrame= tk.Frame(master= schWindow, background = "#D8D7E8")
    prepSlotSTimeLabel = tk.Label(master=prepSlotSTimeFrame, fg = "#4F2C54", background = "#D8D7E8", text="Start Time", font=("Arial", 20))
    prepSlotSTimeLabel.grid(row = 0, column = 0)
    prepSlotSTimeEntry = tk.Entry(prepSlotSTimeFrame, width = 20, fg = '#D7D7D7')
    prepSlotSTimeEntry.bind('<Button>', enterValue)
    prepSlotSTimeEntry.insert(0, ' hh:mm')
    prepSlotSTimeEntry.grid(row=0, column = 1, padx = (35, 0))
    prepSlotSTimeFrame.place(relx = .06, rely = .3)

    #create and display widgets for slot END TIME and confirmation button
    prepSlotETimeFrame= tk.Frame(master= schWindow, background = "#D8D7E8")
    prepSlotETimeLabel = tk.Label(master=prepSlotETimeFrame, fg = "#4F2C54", background = "#D8D7E8", text="End Time", font=("Arial", 20))
    prepSlotETimeLabel.grid(row = 0, column = 0)
    prepSlotETimeEntry = tk.Entry(prepSlotETimeFrame, width = 20, fg = '#D7D7D7')
    prepSlotETimeEntry.bind('<Button>', enterValue)
    prepSlotETimeEntry.insert(0, ' hh:mm')
    prepSlotETimeEntry.grid(row=0, column = 1, padx = (40, 0))
    confirmPrepSlotButtonBorder = tk.Frame(prepSlotETimeFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmPrepSlotButton = tk.Button(master=confirmPrepSlotButtonBorder, text="Confirm Slot", command = validatePrepSlot, fg = "#273A36", activeforeground='white', font = ("Arial", 20), highlightbackground = '#C6D8D9')
    confirmPrepSlotButton.pack()
    confirmPrepSlotButtonBorder.grid(column=2, row = 0, padx = (20,0))
    prepSlotETimeFrame.place(relx = .06, rely = .35)

    #create and display subtitle for decor working slots
    title2Frame = tk.Frame(master= schWindow, background = "#D8D7E8")
    title2Label = tk.Label(master=title2Frame, fg = "#273A36", background = "#D8D7E8", text="Decor Working Hours", font=("Arial", 20,'underline'))
    title2Label.pack()
    title2Frame.place(relx = .13, rely = .5, anchor = 'c')

    #create and display widgets for slot DATE
    decorSlotDateFrame= tk.Frame(master= schWindow, background = "#D8D7E8")
    decorSlotDateLabel = tk.Label(master=decorSlotDateFrame, fg = "#273A36", background = "#D8D7E8", text="Slot Date", font=("Arial", 20))
    decorSlotDateLabel.grid(row = 0, column = 0)
    decorSlotDateEntry = tk.Entry(decorSlotDateFrame, width = 20, fg = '#D7D7D7')
    decorSlotDateEntry.bind('<Button>', enterValue)
    decorSlotDateEntry.insert(0, ' DD/MM/YYYY')
    decorSlotDateEntry.grid(row=0, column = 1, padx = (40, 0))
    decorSlotDateFrame.place(relx = .06, rely = .55)

    #create and display widgets for slot START TIME
    decorSlotSTimeFrame= tk.Frame(master= schWindow, background = "#D8D7E8")
    decorSlotSTimeLabel = tk.Label(master=decorSlotSTimeFrame, fg = "#273A36", background = "#D8D7E8", text="Start Time", font=("Arial", 20))
    decorSlotSTimeLabel.grid(row = 0, column = 0)
    decorSlotSTimeEntry = tk.Entry(decorSlotSTimeFrame, width = 20, fg = '#D7D7D7')
    decorSlotSTimeEntry.bind('<Button>', enterValue)
    decorSlotSTimeEntry.insert(0, ' hh:mm')
    decorSlotSTimeEntry.grid(row=0, column = 1, padx = (35, 0))
    decorSlotSTimeFrame.place(relx = .06, rely = .6)

    #create and display widgets for slot END TIME and confirmation button
    decorSlotETimeFrame= tk.Frame(master= schWindow, background = "#D8D7E8")
    decorSlotETimeLabel = tk.Label(master=decorSlotETimeFrame, fg = "#273A36", background = "#D8D7E8", text="End Time", font=("Arial", 20))
    decorSlotETimeLabel.grid(row = 0, column = 0)
    decorSlotETimeEntry = tk.Entry(decorSlotETimeFrame, width = 20, fg = '#D7D7D7')
    decorSlotETimeEntry.bind('<Button>', enterValue)
    decorSlotETimeEntry.insert(0, ' hh:mm')
    decorSlotETimeEntry.grid(row=0, column = 1, padx = (40, 0))
    confirmDecorSlotButtonBorder = tk.Frame(decorSlotETimeFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmDecorSlotButton = tk.Button(master=confirmDecorSlotButtonBorder, text="Confirm Slot", command = validateDecorSlot, fg = "#273A36", activeforeground='white', font = ("Arial", 20), highlightbackground = '#C6D8D9')
    confirmDecorSlotButton.pack()
    confirmDecorSlotButtonBorder.grid(column=2, row = 0, padx = (20,0))
    decorSlotETimeFrame.place(relx = .06, rely = .65)

    #create and display graphical schedule for current week
    global tempSlots
    global schedule
    global currentWeekShown
    currentWeekShown = str(today - timedelta(days=today.weekday()))[:10]
    schedule = create_graphical_schedule(currentWeekShown, tempSlots, schWindow)
    schedule.place(relx = .5, rely = .25)

    #create and display arrow buttons below graphical schedule
    global arrowIconRight
    global arrowIconLeft
    arrowFrame = tk.Frame(master=schWindow)
    arrowFrame.configure(background = "#D8D7E8")
    arrowButtonLeft = tk.Button(master=arrowFrame, image = arrowIconLeft, width = 30, height = 30, command = changeShownWeekLeft)
    arrowButtonLeft.grid(column = 0, row = 0)
    arrowButtonRight = tk.Button(master=arrowFrame, image = arrowIconRight, width = 30, height = 30, command = changeShownWeekRight)
    arrowButtonRight.grid(column = 1, row = 0, padx = 30)
    arrowFrame.place(relx=.68, rely=.74)

    #create and place button to close window when all slots entered
    confirmFrame = tk.Frame(master=schWindow)
    confirmFrame.configure(pady=50, background = "#D8D7E8")
    confirmButtonBorder = tk.Frame(confirmFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, text="Confirm",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), command = closeModule, highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.grid(column=0, row = 0)
    #create and place button to cancel slots entry
    cancelButtonBorder = tk.Frame(confirmFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    cancelButton = tk.Button(master=cancelButtonBorder, text="Cancel", activeforeground='white', command = closeModuleCancel, fg = "#273A36",   font = ("Arial", 25), highlightbackground = '#C6D8D9')
    cancelButton.pack()
    cancelButtonBorder.grid(column=1, row = 0, padx = 40)
    confirmFrame.place(relx=.40, rely=.77)

    #open window on top of previous one and pass execution to it
    schWindow.geometry("1400x800+110+20")
    schWindow.configure(background = "#D8D7E8")
    schWindow.mainloop()



#displays packaging entry page
def addEditPackaging():

    #allows user to fully logout if this page has been opened in a new window 
    def logOutFromNewWindow():
        global newWindowFlag
        newWindowFlag = False
        win = changeScreen()
        window2.destroy()
        registration_login()

    #call change screen module once page opened
    win = changeScreen()
    global newWindowFlag
    #determine whether page needs opening in a new window or existing one
    if newWindowFlag == False:
        window2 = welcomeWindow
        #destroy all widgets on page except login/info buttons and title
        for widget in window2.winfo_children():
            global logOutButtonBorder
            global infoButtonBorder
            global title
            if widget != logOutButtonBorder and  widget != title and  widget != infoButtonBorder:
                widget.destroy()
            #set title widget to correct text
            title.configure(text = 'Add/Edit Packaging')
            title.place(relx =.5, rely = .1, anchor = 'c')
    else:
        #create new window and recreate logout/info buttons and title
        window2 = tk.Toplevel()
        window2.grab_set()
        newlogOutButtonBorder = tk.Frame(master=window2, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        newlogOutButton = tk.Button(master=newlogOutButtonBorder, command = logOutFromNewWindow, justify = 'center', text = '-->', width = 7, height = 4)
        newlogOutButton.pack()
        newlogOutButtonBorder.place(relx = .05, rely = .06)
        newtitle = tk.Label(master=window2, fg = "#4F2C54", text = 'Add/Edit Packaging', bg = "#D8D7E8", font=("Courier", 80))
        newtitle.place(relx =.5, rely = .1, anchor = 'c')
        newinfoButtonBorder = tk.Frame(master=window2, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        newinfoButton = tk.Button(master=newinfoButtonBorder, text = "?", width = 2, font = ("Arial", 50),highlightbackground = '#C6D8D9')
        newinfoButton.pack()
        newinfoButtonBorder.place(relx = .85, rely = .06)
        
    #triggered when packaging is fully validated or cancelled, and page needs to be closed
    def closeModule():
        global newWindowFlag
        global previous
        #check if page was opened in new window 
        if newWindowFlag == True:
            if newPackagingEntry.winfo_ismapped() == True:
                #fetch new item name 
                newItem = newPackagingEntry.get()
            else:
                newItem = packagingCombo.get()
            #place name in widget on page it was called from 
            for widget in previous[len(previous)-2].winfo_children():
                if widget.winfo_class() == 'Frame':
                    for item in widget.winfo_children():
                        try:
                            if item.get() == ' + New Packaging Item':
                                item.delete(0, tk.END)
                                item.insert(0, newItem)
                        except:
                            pass
            #close new window and return execution
            previous.pop()
            window2.grab_release()
            window2.destroy()
        else:
            newWindowFlag == False
            homepage()

    #validates all entered fields and updates database
    def validate():
        invalidFields = []
        global existingItemFlag
        #checking packaging item field
        itemEntered = packagingCombo.get()
        mycursor.execute("SELECT ItemName FROM tblPackagingItems")
        flag = False
        if itemEntered == ' + New Packaging Item':
            flag = True
        else:
            for record in mycursor:
                if itemEntered == record[0]:
                    #matches an existing batch size as needed
                    flag = True

        #determines whether an item has been selected by checking if the selection has triggered the bulk purchase quantity widget to be displayed yet
        global bulkPurchaseQtyEntry
        try:
            if bulkPurchaseQtyEntry.winfo_ismapped() == False:
                flag = False
        except:
            flag = False
        
        #invalid if item entered by user is blank, not stored in database or not '+ New...'
        if flag == False:
            invalidFields.append('Packaging Item Name')
            invalidFields = ', '.join(invalidFields)
            existingItemFlag = False
            validationPopup(invalidFields)
        
        #checking new item field
        if newPackagingEntry.winfo_ismapped() == True:
            itemEntered = newPackagingEntry.get()
            if (itemEntered.isspace() == True) or (itemEntered == ''):
                #invalid if new item name left blank
                invalidFields.append('New Packaging Item Name')

        bulkPurchaseQty = bulkPurchaseQtyEntry.get()
        floatFlag = isfloat(bulkPurchaseQty)
        if bulkPurchaseQty == '' or bulkPurchaseQty.isspace() == True or floatFlag == False:
            invalidFields.append('Bulk Purchase Quantity')

        global qtyInStockEntry
        qtyInStock = qtyInStockEntry.get()
        floatFlag = isfloat(qtyInStock)
        if qtyInStock == '' or qtyInStock.isspace() == True or floatFlag == False:
            #invalid if blank or not a float
            invalidFields.append('Quantity in Stock')

        #initialise flag
        existingItemFlag = False

        #display error message popup if any invalid fields were identified
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            validationPopup(invalidFields)
        else:
            #check new item name chosen is not already taken by a stored item
            if packagingCombo.get() == ' + New Packaging Item':
                mycursor.execute("SELECT ItemName FROM tblPackagingItems")
                allitems = mycursor.fetchall()
                itemEntered = newPackagingEntry.get()
                for item in allitems:
                    if itemEntered == item[0]:
                        #display error message
                        existingItemFlag = True
                        validationPopup('')
                if existingItemFlag == False:
                    #add item to database
                    mycursor.execute("INSERT INTO tblPackagingItems (ItemName, PurchaseQuantity, QuantityInStock) VALUES ('" + itemEntered + "', '" + bulkPurchaseQty + "', '" + qtyInStock + "')")
                    mydb.commit()
                    mycursor.execute("SELECT PackagingID FROM tblPackagingItems WHERE ItemName = '" + itemEntered + "' and PurchaseQuantity = '" + bulkPurchaseQty + "' and QuantityInStock = '" + qtyInStock + "'")
                    itemID = mycursor.fetchall()[0][0]
                    packagingRestock(itemID, today)
                    closeModule()

            else:
                #all valid - update existing item in database
                mycursor.execute("UPDATE tblPackagingItems SET PurchaseQuantity = '" + bulkPurchaseQty + "', QuantityInStock = '" + qtyInStock + "' WHERE ItemName = '" + str(itemEntered) + "'")
                mydb.commit()
                mycursor.execute("SELECT PackagingID FROM tblPackagingItems WHERE ItemName = '" + str(itemEntered) + "' and PurchaseQuantity = '" + bulkPurchaseQty + "' and QuantityInStock = '" + qtyInStock + "'")
                itemID = mycursor.fetchall()[0][0]
                packagingRestock(itemID, today)
                closeModule()

    #creates and displays popup window to alert user of any invalid field entries on page        
    def validationPopup(invalidFields):
        global validationPopupWindow
        validationPopupWindow = tk.Toplevel()
        window2.grab_release()
        validationPopupWindow.grab_set()

        #change message depending on invalid fields
        global existingItemFlag
        if existingItemFlag != True:
            #format text so it fits in dimension of window and place
            clarificationText = textwrap.wrap("Please enter a valid " + invalidFields, width = 50, break_long_words = False, placeholder = '')
        else:
            clarificationText = textwrap.wrap("Packaging Item name is already taken. Please enter a different name.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=validationPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=validationPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeValidationPopup, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it#open window and pass execution to it
        validationPopupWindow.geometry("600x500+360+140")
        validationPopupWindow.configure(background = "#C6D8D9")
        validationPopupWindow.mainloop()

    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeValidationPopup():
        global validationPopupWindow
        validationPopupWindow.grab_release()
        validationPopupWindow.destroy()

    #name window and add as previous window 
    window2.title("Packaging Window")
    global previous
    if newWindowFlag == True:
        previous.append(window2)
    else:
        previous = [window2]
    global infoButtonMessage
    infoButtonMessage = 'packaging'
    
    global infoButton
    #infoButton.configure(command = addOrderInfo )

    #display explanation popup window for entering a bulk purchase quantity when user clicks '?' button
    def bulkPurchaseQtyInfo():
        global bulkPurchaseQtyInfoWindow
        bulkPurchaseQtyInfoWindow = tk.Toplevel()
        bulkPurchaseQtyInfoWindow.grab_set()

        #format text so it fits in dimension of window and place
        clarificationText = textwrap.wrap("For simplicity, packaging items can only be bought in one standard bulk amount. You should enter this as the largest amount you can purchase at once, for example, 50 cake boxes.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=bulkPurchaseQtyInfoWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .45, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=bulkPurchaseQtyInfoWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeBulkPurchaseQtyInfo, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.85)    

        #open window and pass execution to it
        bulkPurchaseQtyInfoWindow.geometry("600x500+360+140")
        bulkPurchaseQtyInfoWindow.configure(background = "#C6D8D9")
        bulkPurchaseQtyInfoWindow.mainloop()

    #triggered when close button is pressed, to close popup window and pass back execution
    def closeBulkPurchaseQtyInfo():
        global bulkPurchaseQtyInfoWindow
        bulkPurchaseQtyInfoWindow.grab_release()
        bulkPurchaseQtyInfoWindow.destroy()
        
    #triggered when an item is selected so other page widgets can be displayed/reset 
    def showOtherFields(event):
        global row2Frame
        global row3Frame
        global bulkPurchaseQtyEntry
        global qtyInStockEntry

        if packagingCombo.get() == ' + New Packaging Item':
            #show new name entry fields
            newPackagingLabel.grid(row = 0, column = 3, padx = (30,10))
            newPackagingEntry.grid(row = 0, column = 4)
        else:
           #remove new name entry fields
           newPackagingLabel.grid_forget()
           newPackagingEntry.grid_forget()

           
        try:
            #clear widgets and display extra ones if exist already 
            bulkPurchaseQtyEntry.delete(0,tk.END)
            qtyInStockEntry.delete(0,tk.END)
            row2Frame.place(relx = .05, rely = .35)
            row3Frame.place(relx = .09, rely = .45)
        except:
            #create and display new widgets for bulk purchase quantity and quantity in stock
            row2Frame = tk.Frame(master= window2, background = "#D8D7E8")
            bulkQtyClarifyButton = tk.Button(master=row2Frame, command = bulkPurchaseQtyInfo, text = '?', width = 4, height = 2)
            bulkQtyClarifyButton.grid(row=0, column = 0, padx = (0,20))
            bulkPurchaseQtyLabel = tk.Label(master=row2Frame, fg = "#4F2C54", background = "#D8D7E8", text="Bulk Purchase" + "\n" + "Quantity (units)", font=("Arial", 20))
            bulkPurchaseQtyLabel.grid(row = 0, column = 1)
            bulkPurchaseQtyEntry = tk.Entry(row2Frame, width = 30)
            bulkPurchaseQtyEntry.grid(row=0, column =2, padx = (30, 0))
            row2Frame.place(relx = .05, rely = .35)

            row3Frame = tk.Frame(master= window2, background = "#D8D7E8")
            qtyInStockLabel = tk.Label(master=row3Frame, fg = "#4F2C54", background = "#D8D7E8", text="Quantity in" + "\n" + "Stock (units)", font=("Arial", 20))
            qtyInStockLabel.grid(row = 0, column = 0)
            qtyInStockEntry = tk.Entry(row3Frame, width = 30)
            qtyInStockEntry.grid(row=0, column =1, padx = (30, 0))
            row3Frame.place(relx = .09, rely = .45)

        #fetch item name from page
        if packagingCombo.get() == ' + New Packaging Item':
            itemEntered = newPackagingEntry.get()
        else:
            itemEntered = packagingCombo.get()
        #fetch purchasable quantity and quantity in stock from database for entered item
        mycursor.execute("SELECT PurchaseQuantity, QuantityInStock FROM tblPackagingItems WHERE ItemName = '" + itemEntered + "'")
        records = mycursor.fetchall()
        #insert these quantities into entry widgets on page
        bulkPurchaseQtyEntry.delete(0, tk.END)
        bulkPurchaseQtyEntry.insert(0, records[0][0])
        qtyInStockEntry.delete(0, tk.END)
        qtyInStockEntry.insert(0, records[0][1])        

    #create widgets for first row of page 
    global packagingCombo
    row1Frame = tk.Frame(master= window2, background = "#D8D7E8")
    packagingLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="Packaging", font=("Arial", 20), justify = 'right')
    packagingLabel.grid(row=0, column = 0)
    searchButton = tk.Button(row1Frame, text='Search')
    searchButton.grid(row=0, column = 2, padx = (3,0))
    searchButton.bind('<Button>', searchForPackaging)
    packagingCombo = ttk.Combobox(row1Frame, textvariable=tk.StringVar(), width =30, values=[' + New Packaging Item'], style = "TCombobox")
    packagingCombo.grid(row=0, column = 1, padx = (39,0))
    #check if new item is immediately being entered when called from another page with '+ New Packaging Item'
    global newPackagingFlag
    if newPackagingFlag == True:
        packagingCombo.insert(0, ' + New Packaging Item')
        #trigger showOtherFields function to show new fields as soon as new window opened
        packagingCombo.bind('<Map>', showOtherFields)
    packagingCombo.bind('<<ComboboxSelected>>', showOtherFields)
    newPackagingLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="New Packaging Item Name", font=("Arial", 20))
    newPackagingEntry = tk.Entry(row1Frame, width = 30)
    row1Frame.place(relx = .09, rely = .25)
    pairing[searchButton] = packagingCombo

    #create and place button to close window when item validated 
    confirmFrame = tk.Frame(master=window2)
    confirmFrame.configure(pady=50, background = "#D8D7E8")
    confirmButtonBorder = tk.Frame(confirmFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    confirmButton = tk.Button(master=confirmButtonBorder, text="Confirm",  fg = "#273A36", command= validate, activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
    confirmButton.pack()
    confirmButtonBorder.grid(column=0, row = 0)
    #create and place button to cancel item
    cancelButtonBorder = tk.Frame(confirmFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
    cancelButton = tk.Button(master=cancelButtonBorder, text="Cancel", activeforeground='white', fg = "#273A36",  command = closeModule, font = ("Arial", 25), highlightbackground = '#C6D8D9')
    cancelButton.pack()
    cancelButtonBorder.grid(column=1, row = 0, padx = 40)
    confirmFrame.place(relx=.40, rely=.67)

    #if page should be opening in new window, open window on top of previous one and pass execution to it
    if newWindowFlag == True:
        window2.geometry("1400x800+110+20")
        window2.configure(background = "#D8D7E8")
        window2.mainloop()

#displays add order entry page
def addOrder():
    #call change screen module once page opened 
    win = changeScreen()
    #destroy all widgets on page except login/info buttons and title
    for widget in welcomeWindow.winfo_children():
        global logOutButtonBorder
        global infoButtonBorder
        global title
        if widget != logOutButtonBorder and  widget != title and  widget != infoButtonBorder:
            widget.destroy()
        #set title widget to correct text
        title.configure(text = 'Add Order')
        title.place(relx =.5, rely = .1, anchor = 'c')

    #name window and add as previous window 
    global previous
    previous = [welcomeWindow]
    welcomeWindow.title("Add Order Window")

    #set message popup for info button as addOrderInfo
    global infoButtonMessage
    infoButtonMessage = 'addOrder'

    global tempSlots
    tempSlots = []

    #triggered whenever a new widget is clicked
    def enterValue(event):
        try:
            if event.widget != orderDateEntry:
                if orderDateEntry.get().isspace() == True or orderDateEntry.get() == '':
                     #re-enters format placeholder in empty date widget  
                     orderDateEntry.configure(fg = '#D7D7D7')
                     orderDateEntry.delete(0, tk.END)
                     orderDateEntry.insert(0, ' DD/MM/YYYY')
            else:
                if orderDateEntry.get().isspace() == True or orderDateEntry.get() == '' or orderDateEntry.get() == ' DD/MM/YYYY':
                    #deletes format placeholder in clicked widget so user can enter text
                    orderDateEntry.delete(0, tk.END)
                    orderDateEntry.configure(fg = 'black')
        except:
           pass

    #triggered when a recipe-batch pair is entered and 'add' button clicked to validate
    def checkRecipeAndBatch():
        invalidFields = []
        #fetch recipe from page and check valid
        recipeEntered = recipeCombo1.get()
        mycursor.execute("SELECT RecipeName FROM tblBaseRecipe")
        flag = False
        for record in mycursor:
             if recipeEntered == record[0]:
                 #matches an existing recipe as needed
                 flag = True
                    
        if flag == False:
            #invalid if recipe entered is not stored in database
            invalidFields.append('Recipe Name')
        else:
            global recipeForNewBatchSize
            recipeForNewBatchSize = recipeEntered
            global batchCombo1
            #fetch batch from page and check valid 
            batchEntered = batchCombo1.get()
            mycursor.execute("SELECT BatchSizeName, BatchID FROM tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipeEntered + "' AND tblBaseRecipe.RecipeID = tblBatchSize.RecipeID")
            flag = False
            for record in mycursor:
                if batchEntered == record[0]:
                     #matches an existing batch size for THIS recipe as needed
                     flag = True
                     
            if flag == False:
                #invalid if batch entered is not stored in database for this recipe
                invalidFields.append('Batch Size')

            #display error message popup if any invalid fields were identified 
            invalidFields = ', '.join(invalidFields)
            if invalidFields != '':
                validationPopup(invalidFields)
            else:
                #save and show entered pair on page
                addRecipe()
                
    #triggered when a prep ingredient is entered and 'add' button clicked to validate
    def checkPrepIng():
        invalidFields = []
        #fetch ingredient-quantity pair from page and check valid
        prepIngEntered = additionalPrepIngsCombo.get()
        quantityEntered = quantityEntry.get()
        mycursor.execute("SELECT IngredientName FROM tblBaseIngredient")
        flag = False
        for record in mycursor:
             if prepIngEntered == record[0]:
                 #matches an existing ingredient as needed
                 flag = True
                    
        if flag == False:
            #invalid if ingredient entered is not stored in database
            invalidFields.append('Prep Ingredient')
        else:
            floatFlag = isfloat(quantityEntered)
            if quantityEntered.isspace == True or quantityEntered == '' or floatFlag == False:
                #invalid if quantity entered is blank or not a float
                invalidFields.append('Ingredient Quantity')

        #display error message popup if any invalid fields were identified
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            global existingOrderFlag
            existingOrderFlag = False
            validationPopup(invalidFields)
        else:
            #save and show entered pair on page
            addPrepIngs()

    #triggered when a decor ingredient is entered and 'add' button clicked to validate
    def checkDecorIng():
        invalidFields = []
        #fetch ingredient-quantity pair from page and check valid
        decorIngEntered = additionalDecorIngsCombo.get()
        quantityEntered = quantityEntry2.get()
        mycursor.execute("SELECT IngredientName FROM tblBaseIngredient")
        flag = False
        for record in mycursor:
             if decorIngEntered == record[0]:
                 #matches an existing ingredient as needed
                 flag = True
                    
        if flag == False:
            #invalid if ingredient entered is not stored in database
            invalidFields.append('Decor Ingredient')
        else:
            floatFlag = isfloat(quantityEntered)
            if quantityEntered.isspace == True or quantityEntered == '' or floatFlag == False:
                #invalid if quantity entered is blank or not a float
                invalidFields.append('Ingredient Quantity')

        #display error message popup if any invalid fields were identified
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            global existingOrderFlag
            existingOrderFlag = False
            validationPopup(invalidFields)
        else:
            #save and show entered pair on page
            addDecorIngs()

    #triggered when a packaging item is entered and 'add' button clicked to validate
    def checkPackagingItem():
        invalidFields = []
        #fetch item-quantity pair from page and check valid
        packagingEntered = packagingItemCombo.get()
        quantityEntered = quantityEntry3.get()
        mycursor.execute("SELECT ItemName FROM tblPackagingItems")
        flag = False
        for record in mycursor:
             if packagingEntered == record[0]:
                 #matches an existing item as needed
                 flag = True
                    
        if flag == False:
            #invalid if item entered is not stored in database
            invalidFields.append('Packaging Item')
        else:
            floatFlag = isfloat(quantityEntered)
            if quantityEntered.isspace == True or quantityEntered == '' or floatFlag == False:
                #invalid if quantity entered is blank or not a float
                invalidFields.append('Packaging Quantity')

        #display error message popup if any invalid fields were identified
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            global existingOrderFlag
            existingOrderFlag = False
            validationPopup(invalidFields)
        else:
            #save and show entered pair on page
            addPackaging()

    #validates all entered fields and updates database               
    def validate():
        invalidFields = []
        
        #checking order name field
        orderNameEntered = orderNameEntry.get()
        if orderNameEntered.isspace() == True or orderNameEntered == '':
            #invalid if blank
            invalidFields.append('Order Name')

        #checking order date
        orderDateEntered = orderDateEntry.get()
        if orderDateEntered == '' or orderDateEntered.isspace() == True:
            #invalid if blank 
            invalidFields.append('Order Date')
        try:
            orderDateEntered = datetime.strptime(orderDateEntered, "%d/%m/%Y")
            if orderDateEntered.date() < today:
                #invalid if date is before today's date
                invalidFields.append('Order date')
        except ValueError:
            #invalid if not a valid date format
            invalidFields.append('Order Date')

        #checking unentered recipe/batches
        recipeEntered = recipeCombo1.get()
        if recipeEntered.isspace != True and recipeEntered != '':
            #invalid if any text left in either entry widget
            invalidFields.append('Recipe-Batch Pair')

        #checking unentered prep ings
        prepIngEntered = additionalPrepIngsCombo.get()
        if prepIngEntered.isspace != True and prepIngEntered != '':
            #invalid if any text left in either entry widget
            invalidFields.append('Prep Ingredient')

        #checking unentered decor ings
        decorIngEntered = additionalDecorIngsCombo.get()
        if decorIngEntered.isspace != True and decorIngEntered != '':
            #invalid if any text left in either entry widget
            invalidFields.append('Decor Ingredient')

        #checking unentered packaging 
        packagingEntered = packagingItemCombo.get()
        if packagingEntered.isspace != True and packagingEntered != '':
            #invalid if any text left in either entry widget
            invalidFields.append('Packaging Item')

        #checking if no working slots entered
        global tempSlots
        prepFlag = False
        decorFlag = False
        for slot in tempSlots:
            if slot[4] == 'PREP':
                prepFlag = True
            elif slot[4] == 'DECOR':
                decorFlag = True
        if decorFlag == False and prepFlag == False:
            invalidFields = ['At least one prep and one decor slot']
        elif decorFlag == False:
            invalidFields = ['At least one decor slot']
        elif prepFlag == False:
            invalidFields = ['At least one prep slot']

        #initialise flag  
        global existingOrderFlag
        existingOrderFlag = False

        #display error message popup if any invalid fields were identified
        invalidFields = ', '.join(invalidFields)
        if invalidFields != '':
            validationPopup(invalidFields)
        else:
            #check new order name chosen is not already taken by a stored order
            mycursor.execute("SELECT OrderName FROM tblCustomerOrder")
            allorders = mycursor.fetchall()
            for order in allorders:
                if orderNameEntered == order[0]:
                    #display error message
                    existingOrderFlag = True
                    validationPopup('')
            if existingOrderFlag == False:
                #fetch additional notes from page
                additionalNotes = addNotesEntry.get()
                #insert order into database and fetch ID to use 
                mycursor.execute("INSERT INTO tblCustomerOrder (OrderName, OrderDate, AdditionalNotes) VALUES ('" + orderNameEntered + "', '" + str(orderDateEntered) + "', '" + additionalNotes + "')")
                mydb.commit()
                mycursor.execute("SELECT OrderID FROM tblCustomerOrder WHERE OrderName = '"+ orderNameEntered + "'")
                orderID = mycursor.fetchall()[0][0]
                #insert each validated recipe-batch pair into database for this order
                for item in enteredRecipesList:
                    recipe = item[0]
                    batch = item[1]
                    #find batchID for pair
                    mycursor.execute("SELECT BatchID FROM tblBatchSize, tblBaseRecipe WHERE RecipeName = '" + recipe + "' AND BatchSizeName = '" + batch + "' and tblBaseRecipe.RecipeID = tblBatchSize.RecipeID")
                    batchID = mycursor.fetchall()[0][0]
                    mycursor.execute("INSERT INTO tblBatchSizeInOrder (OrderID, BatchID, DateRequired, EndDateRequired) VALUES ( '" + str(orderID) + "', '" + str(batchID) +"', '', '')")
                #insert each validated prepIngredient-quantity pair into database for this order
                for i in range(0, len(enteredPrepIngsList)):
                    ingredient = enteredPrepIngsList[i][0]
                    quantity = enteredPrepIngsList[i][1]
                    global criticalPrepList
                    #find ingredientID for pair
                    mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '" + ingredient + "' ")
                    ingredientID = mycursor.fetchall()[0][0]
                    #determine whether to add as critical or non-critical then add to database
                    critical = criticalPrepList[i]
                    if critical == ():
                        mycursor.execute("INSERT INTO tblBaseIngredientInOrder (OrderID, IngredientID, Quantity, IngredientType, Critical, DateRequired, EndDateRequired) VALUES ( '" + str(orderID) + "', '" + str(ingredientID) +"', '" + quantity + "', 'PREP', '0', '', '')")
                    elif critical[0] == ('alternate'):
                        mycursor.execute("INSERT INTO tblBaseIngredientInOrder (OrderID, IngredientID, Quantity, IngredientType, Critical, DateRequired, EndDateRequired) VALUES ( '" + str(orderID) + "', '" + str(ingredientID) +"', '" + quantity + "', 'PREP', '0', '', '')")
                    else:
                        mycursor.execute("INSERT INTO tblBaseIngredientInOrder (OrderID, IngredientID, Quantity, IngredientType, Critical, DateRequired, EndDateRequired) VALUES ( '" + str(orderID) + "', '" + str(ingredientID) +"', '" + quantity + "', 'PREP', '1', '', '')")
                #insert each validated decorIngredient-quantity pair into database for this order
                for i in range(0, len(enteredDecorIngsList)):
                    ingredient = enteredDecorIngsList[i][0]
                    quantity = enteredDecorIngsList[i][1]
                    global criticalDecorList
                    #find ingredientID for pair
                    mycursor.execute("SELECT IngredientID FROM tblBaseIngredient WHERE IngredientName = '" + ingredient + "' ")
                    ingredientID = mycursor.fetchall()[0][0]
                    #determine whether to add as critical or non-critical then add to database
                    critical = criticalDecorList[i]
                    if critical == ():
                        mycursor.execute("INSERT INTO tblBaseIngredientInOrder (OrderID, IngredientID, Quantity, IngredientType, Critical, DateRequired, EndDateRequired) VALUES ( '" + str(orderID) + "', '" + str(ingredientID) +"', '" + quantity + "', 'DECOR', '0', '', '')")
                    elif critical[0] == ('alternate'):
                        mycursor.execute("INSERT INTO tblBaseIngredientInOrder (OrderID, IngredientID, Quantity, IngredientType, Critical, DateRequired, EndDateRequired) VALUES ( '" + str(orderID) + "', '" + str(ingredientID) +"', '" + quantity + "', 'DECOR', '0', '', '')")
                    else:
                        mycursor.execute("INSERT INTO tblBaseIngredientInOrder (OrderID, IngredientID, Quantity, IngredientType, Critical, DateRequired, EndDateRequired) VALUES ( '" + str(orderID) + "', '" + str(ingredientID) +"', '" + quantity + "', 'DECOR', '1', '', '')")
                #insert each validated packaging-quantity pair into database for this order
                for pair in enteredPackagingList:
                    item = pair[0]
                    quantity = pair[1]
                    #find packagingID for pair
                    mycursor.execute("SELECT PackagingID FROM tblPackagingItems WHERE ItemName = '" + item + "' ")
                    packagingID = mycursor.fetchall()[0][0]
                    mycursor.execute("INSERT INTO tblPackagingItemInOrder VALUES ( '" + str(orderID) + "', '" + str(packagingID) +"', '" + quantity + "')")
                #insert tempSlots (passed from addWorkingHours page) into database for this order
                for slot in tempSlots:
                    mycursor.execute("INSERT INTO tblWorkingDateSlot VALUES ('" + str(orderID) + "', '" + str(slot[1]) + "', '" + str(slot[2]) + "', '" + str(slot[3]) + "', '" + str(slot[4])+ "')")
                mydb.commit()
                #schedule initial shopping dates for this order
                initialShopDateScheduling(orderID)
                shoppingOptimisation()
                homepage()

    #creates and displays popup window to alert user of any invalid field entries on page
    def validationPopup(invalidFields):
        global validationPopupWindow
        validationPopupWindow = tk.Toplevel()
        validationPopupWindow.grab_set()

        #change message depending on invalid fields
        global existingOrderFlag
        if existingOrderFlag != True:
            #format text so it fits in dimension of window and place
            clarificationText = textwrap.wrap("Please enter a valid " + invalidFields, width = 50, break_long_words = False, placeholder = '')
        else:
            clarificationText = textwrap.wrap("Order name is already taken. Please enter a different name.", width = 50, break_long_words = False, placeholder = '')
        clarificationMessageFrame = tk.Frame(master=validationPopupWindow, background = "#C6D8D9")
        for line in clarificationText:
            clarificationMessage = tk.Label(master=clarificationMessageFrame, fg = "#273A36", background = "#C6D8D9", text= line, font=("Arial", 20))
            clarificationMessage.pack()
        clarificationMessageFrame.place(relx = .5, rely = .40, anchor = 'c')

        #create button to close window once user has read explanation message and place
        buttonsFrame = tk.Frame(master=validationPopupWindow)
        buttonsFrame.configure(pady=10, background = "#C6D8D9")
        confirmButtonBorder = tk.Frame(buttonsFrame, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
        confirmButton = tk.Button(master=confirmButtonBorder, command = closeValidationPopup, text= "  Got it  ",  fg = "#273A36", activeforeground='white', font = ("Arial", 25), highlightbackground = '#C6D8D9')
        confirmButton.pack()
        confirmButtonBorder.pack()
        buttonsFrame.place(relx=.40, rely=.80)    

        #open window and pass execution to it#open window and pass execution to it
        validationPopupWindow.geometry("600x500+360+140")
        validationPopupWindow.configure(background = "#C6D8D9")
        validationPopupWindow.mainloop()

    #triggered when confirm button is pressed, to close popup window and pass back execution
    def closeValidationPopup():
        global validationPopupWindow
        validationPopupWindow.grab_release()
        validationPopupWindow.destroy()        

    #checks if the user wants the order to contain something new so a 'New ...' module will need to run
    def checkForModuleChange(event):
        global newWindowFlag
        global newIngredientFlag
        global newRecipeFlag
        global newPackagingFlag
        global newBatchFlag
        global batchCombo1
        #check for new recipe and open page
        if recipeCombo1.get() == ' + New Recipe':
            newWindowFlag = True
            newRecipeFlag = True
            addBaseRecipe()
        #check for new prep ingredient and open page
        elif additionalPrepIngsCombo.get() == ' + New Ingredient':
            newWindowFlag = True
            newIngredientFlag = True
            addIngredient()
        #check for new decor recipe and open page
        elif additionalDecorIngsCombo.get() == ' + New Ingredient':
            newIngredientFlag = True
            newWindowFlag = True
            addIngredient()
        #check for new packaging item and open page
        elif packagingItemCombo.get() == ' + New Packaging Item':
            newWindowFlag = True
            newPackagingFlag = True
            addEditPackaging()
        #check for new batch and open page
        elif batchCombo1.get() == ' + New Batch Size':
            newWindowFlag = True
            newBatchFlag = True
            addBatchSize()

    #clear/remove widgets from page once recipe added, and display added recipe on page
    def addRecipe():
        global recipeCombo1
        global batchCombo1
        global batchLabel
        global searchButton2
        global addRecipeButton
        global enteredRecipesListLabel
        global enteredRecipesList
        #fetch recipe and batch entered
        recipe = recipeCombo1.get()
        batchSize = batchCombo1.get()
        #remove batch widgets and add button
        batchLabel.grid_remove()
        batchCombo1.grid_remove()
        searchButton2.grid_remove()
        addRecipeButton.grid_remove()
        #reset recipe combo
        recipeCombo1.delete(0, tk.END)
        recipeCombo1.configure(values=[' + New Recipe'])
        #add recipe-batch pair to list and format to display on page
        enteredRecipesList.append((recipe, batchSize))
        enteredRecipesListToShow = ['{} - {}'.format(recipe, batchSize) for recipe, batchSize in enteredRecipesList]
        enteredRecipesListLabel.configure(text = 'Entered: ' + ', '.join(enteredRecipesListToShow))
        enteredRecipesListLabel.place(relx = .5, rely = .34, anchor='c')

    #clear/remove widgets from page once prep ingredient added, and display added ingredient on page
    def addPrepIngs():
        global enteredPrepIngsListLabel
        global enteredPrepIngsList
        global additionalPrepIngsCombo
        global quantityEntry
        global criticalPrepIngs
        global enteredPrepIngsList
        global criticalPrepIngsList
        #fetch ingredient and values entered
        ingredient = additionalPrepIngsCombo.get()
        quantity =  quantityEntry.get()
        critical = criticalPrepIngs.state()
        #clear all widgets 
        additionalPrepIngsCombo.delete(0, tk.END)
        quantityEntry.delete(0, tk.END)
        #add ingredient-quantity and ingredient-critical pairs to dictionary and format to display on page
        enteredPrepIngsList.append((ingredient, quantity))
        criticalPrepList.append(critical)
        enteredPrepIngsListToShow = []
        for item in enteredPrepIngsList:
            key = item[0]
            value = item[1]
            #fetch ingredient unit from database and display with ingredient
            mycursor.execute("SELECT QuantityUnit from tblBaseIngredient WHERE IngredientName = '" + key + "'")
            unit = mycursor.fetchall()[0][0]
            enteredPrepIngsListToShow.append('{} - {}{}'.format(key, value, unit))
        enteredPrepIngsListLabel.configure(text = 'Entered: ' + ', '.join(enteredPrepIngsListToShow))
        enteredPrepIngsListLabel.place(relx = .5, rely = .48, anchor='c')

    #clear/remove widgets from page once decor ingredient added, and display added ingredient on page
    def addDecorIngs():
        global enteredDecorIngsListLabel
        global enteredDecorIngsList
        global additionalDecorIngsCombo
        global quantityEntry2
        global criticalDecorIngs
        global criticalDecorList
        #fetch ingredient and values entered
        ingredient = additionalDecorIngsCombo.get()
        quantity =  quantityEntry2.get()
        critical = criticalDecorIngs.state()
        #clear all widgets 
        additionalDecorIngsCombo.delete(0, tk.END)
        quantityEntry2.delete(0, tk.END)
        #add ingredient-quantity and ingredient-critical pairs to dictionary and format to display on page
        enteredDecorIngsList.append((ingredient, quantity))
        criticalDecorList.append(critical)
        enteredDecorIngsListToShow = []
        for item in enteredDecorIngsList:
            key = item[0]
            value = item[1]
            #fetch ingredient unit from database and display with ingredient
            mycursor.execute("SELECT QuantityUnit from tblBaseIngredient WHERE IngredientName = '" + key + "'")
            unit = mycursor.fetchall()[0][0]
            enteredDecorIngsListToShow.append('{} - {}{}'.format(key, value, unit))
        enteredDecorIngsListLabel.configure(text = 'Entered: ' + ', '.join(enteredDecorIngsListToShow))
        enteredDecorIngsListLabel.place(relx = .5, rely = .62, anchor='c')

    #clear/remove widgets from page once packaging item added, and display added item on page
    def addPackaging():
        global enteredPackagingListLabel
        global enteredPackagingListToShow
        global enteredPackagingList
        global quantityEntry3
        #fetch ingredient and values entered
        item = packagingItemCombo.get()
        quantity =  quantityEntry3.get()
        #clear all widgets 
        packagingItemCombo.delete(0, tk.END)
        quantityEntry3.delete(0, tk.END)
        #add item-quantity to dictionary and format to display on page
        enteredPackagingList.append((item, quantity))
        enteredPackagingListToShow = ['{} - {}'.format(item, quantity) for item, quantity in enteredPackagingList]
        enteredPackagingListLabel.configure(text = 'Entered: ' + ', '.join(enteredPackagingListToShow))
        enteredPackagingListLabel.place(relx = .5, rely = .7, anchor='c')        

    #triggered when batch size entered for recipe 
    def showOtherFields2(event):
            global batchCombo1
            global addRecipeButton
            try:
                #show add button for recipe-batch pair
                addRecipeButton.grid(row=0, column = 6, padx = (20,0))
            except:
                #create and show button for recipe-batch pair
                addRecipeButton = tk.Button(row3Frame, text='Add', command = checkRecipeAndBatch)
                addRecipeButton.grid(row=0, column = 6, padx = (20,0))
            global recipeForNewBatchSize
            recipeForNewBatchSize = recipeCombo1.get()
            checkForModuleChange(event)    

    ##triggered when recipe selected
    def showOtherFields1(event):
        global recipeCombo1
        global batchCombo1
        global pairing
        global batchLabel
        global searchButton2
        global addRecipeButton
        recipeCombo1.bind('<Button>', enterValue)
        try:
            #display batch widgets 
            batchLabel.grid(row=0, column = 3, padx = (30,0))
            searchButton2.grid(row=0, column = 5, padx = (3,0))
            batchCombo1.set('')
            batchCombo1.configure(values=[' + New Batch Size'])
            batchCombo1.grid(row=0, column = 4, padx = (39,0))
            batchCombo1.bind('<Button>', enterValue)
            batchCombo1.bind('<<ComboboxSelected>>', showOtherFields2)
        except:
            #create and display batch widgets 
            batchLabel = tk.Label(master=row3Frame, fg = "#4F2C54", background = "#D8D7E8", text="Batch Size", font=("Arial", 20))
            batchLabel.grid(row=0, column = 3, padx = (30,0))
            searchButton2 = tk.Button(row3Frame, text='Search')
            searchButton2.grid(row=0, column = 5, padx = (3,0))
            searchButton2.bind('<Button>', enterValue)
            searchButton2.bind('<Button>', searchForBatchSize)
            #set flag to true as initial batch size of recipe can be used in order
            global includeInitial
            includeInitial = True
            batchCombo1 = ttk.Combobox(row3Frame, textvariable=tk.StringVar(), width = 25, values=[' + New Batch Size'], style = "TCombobox")
            batchCombo1.grid(row=0, column = 4, padx = (39,0))
            pairing[searchButton2] = batchCombo1
            batchCombo1.bind('<Button>', enterValue)
            batchCombo1.bind('<<ComboboxSelected>>', showOtherFields2)
        global recipeForNewBatchSize
        recipeForNewBatchSize = recipeCombo1.get()
        checkForModuleChange(event)

    #create and display first row of widgets - order name
    global orderNameEntry
    row1Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    orderNameLabel = tk.Label(master=row1Frame, fg = "#4F2C54", background = "#D8D7E8", text="Order Name", font=("Arial", 20))
    orderNameLabel.grid(row = 0, column = 0)
    orderNameEntry = tk.Entry(row1Frame, width = 100)
    orderNameEntry.bind('<Button>', enterValue) 
    orderNameEntry.grid(row=0, column =1, padx = (30, 0))
    row1Frame.place(relx = .09, rely = .16)

    #create and display second row of widgets - order date
    row2Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    dateClarifyButton = tk.Button(master=row2Frame, text = '?', command = orderDateClarifyPopup, width = 4, height = 2)
    dateClarifyButton.grid(row=0, column = 0, padx = (0,20))
    dateClarifyButton.bind('<Button>', enterValue)
    orderDateLabel = tk.Label(master=row2Frame, fg = "#4F2C54", background = "#D8D7E8", text="Order Date", font=("Arial", 20))
    orderDateLabel.grid(row = 0, column = 1)
    global orderDateEntry
    orderDateEntry = tk.Entry(row2Frame, width = 20, fg = '#D7D7D7')
    orderDateEntry.bind('<Button>', enterValue)
    orderDateEntry.insert(0, ' DD/MM/YYYY')
    orderDateEntry.grid(row=0, column = 2, padx = (40, 0))
    row2Frame.place(relx = .056, rely = .22)

    #create and display third row of widgets - recipe entry
    row3Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    baseRecipeLabel = tk.Label(master=row3Frame, fg = "#4F2C54", background = "#D8D7E8", text="Base Recipe", font=("Arial", 20))
    baseRecipeLabel.grid(row=0, column = 0)
    global recipeCombo1
    recipeCombo1 = ttk.Combobox(row3Frame, textvariable=tk.StringVar(), width = 40, values=[' + New Recipe'], style = "TCombobox")
    recipeCombo1.grid(row=0, column = 1, padx = (20,0))
    recipeCombo1.bind('<Button>', enterValue)
    #create search button and link to recipe combobox
    searchButton = tk.Button(row3Frame, text='Search')
    searchButton.grid(row=0, column = 2)
    searchButton.bind('<Button>', enterValue)
    searchButton.bind('<Button>', searchForRecipe)
    row3Frame.place(relx = .09, rely = .28)
    recipeCombo1.bind('<<ComboboxSelected>>', showOtherFields1)
    global pairing
    pairing[searchButton] = recipeCombo1

    #create and place text for showing added recipe-batch pairs on page 
    global enteredRecipesList
    enteredRecipesList = []
    enteredRecipesListToShow = ', '.join(enteredRecipesList)
    global enteredRecipesListLabel
    enteredRecipesListLabel = tk.Label(master=welcomeWindow, fg = "#4F2C54", background = "#D8D7E8", text = enteredRecipesListToShow, font=("Arial", 15), justify = 'center')
    enteredRecipesListLabel.place(relx = .5, rely = .34,  anchor='c')

    #create and display widgets for additional prep ingredients 
    global additionalPrepIngsCombo
    global quantityEntry
    global criticalPrepIngs
    row4Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    #create clarify button
    addPrepIngsClarifyButton = tk.Button(master=row4Frame, text = '?', command = additionalPrepClarify, width = 4, height = 2)
    addPrepIngsClarifyButton.grid(column = 0, row = 0, padx = 20)
    addPrepIngsClarifyButton.bind('<Button>', enterValue)
    #create label title
    additionalPrepIngsLabel = tk.Label(master=row4Frame, fg = "#4F2C54", background = "#D8D7E8", text="Additional Prep" + '\n' + 'Ingredients', font=("Arial", 20), justify = 'right')
    additionalPrepIngsLabel.grid(row=0, column = 1)
    #create ingredient combobox 
    additionalPrepIngsCombo = ttk.Combobox(row4Frame, textvariable=tk.StringVar(), width =30, values=[' + New Ingredient'], style = "TCombobox")
    additionalPrepIngsCombo.grid(row=0, column = 2, padx = (39,0))
    additionalPrepIngsCombo.bind('<Button>', enterValue)
    additionalPrepIngsCombo.bind('<<ComboboxSelected>>', checkForModuleChange)
    #create button and link to ingredient combo to search
    searchButton3 = tk.Button(row4Frame, text='Search')
    searchButton3.grid(row=0, column = 3, padx = (3,0))
    searchButton3.bind('<Button>', enterValue)
    searchButton3.bind('<Button>', searchForIngredient)
    pairing[searchButton3] = additionalPrepIngsCombo
    #create critical widgets - clarify button and title below checkbox
    criticalFrame = tk.Frame(row4Frame, bg = "#D8D7E8")
    criticalPrepIngs = ttk.Checkbutton(criticalFrame)
    criticalPrepIngs.grid(row=0, column=0)
    criticalLabel = tk.Label(criticalFrame,  bg = "#D8D7E8", text = 'Critical?')
    criticalLabel.grid(row=1, column=0)   
    criticalPrepClarifyButton = tk.Button(master=criticalFrame, command = criticalClarify, text = '?', width = 4, height = 2)
    criticalPrepClarifyButton.grid(row=1, column=1)
    criticalPrepClarifyButton.bind('<Button>', enterValue)
    criticalFrame.grid(row=0, column = 4, padx = (30,10))
    #create quantity title and entry for ingredient
    quantityLabel = tk.Label(master=row4Frame, fg = "#4F2C54", background = "#D8D7E8", text="Quantity", font=("Arial", 15))
    quantityLabel.grid(row = 0, column = 6, padx = (20,0))
    quantityEntry = tk.Entry(row4Frame, width = 10)
    quantityEntry.grid(row=0, column = 7, padx = 10)
    quantityEntry.bind('<Button>', enterValue)
    #create add button when pair is entered
    addPrepIngsButton = tk.Button(row4Frame, text='Add', command = checkPrepIng)
    addPrepIngsButton.grid(row=0, column = 8, padx = (20,0))
    row4Frame.place(relx = .02, rely = .36)

    #create and place text for showing added prep ingredients on page 
    global enteredPrepIngsList
    enteredPrepIngsList = []
    global criticalPrepList
    criticalPrepList = []
    enteredPrepIngsListToShow = ', '.join(enteredPrepIngsList)
    global enteredPrepIngsListLabel
    enteredPrepIngsListLabel = tk.Label(master=welcomeWindow, fg = "#4F2C54", background = "#D8D7E8", text=enteredPrepIngsListToShow, font=("Arial", 15), justify = 'center')
    enteredPrepIngsListLabel.place(relx = .5, rely = .48,  anchor='c')

    #create and display widgets for additional decor ingredients
    global additionalDecorIngsCombo
    global quantityEntry2
    global criticalDecorIngs
    row5Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    #create clarify button
    addDecorIngsClarifyButton = tk.Button(master=row5Frame, text = '?', command = additionalDecorClarify, width = 4, height = 2)
    addDecorIngsClarifyButton.grid(column = 0, row = 0, padx = 20)
    addDecorIngsClarifyButton.bind('<Button>', enterValue)
    #create label title
    additionalDecorIngsLabel = tk.Label(master=row5Frame, fg = "#4F2C54", background = "#D8D7E8", text="Additional Decor" + '\n' + 'Ingredients', font=("Arial", 20), justify = 'right')
    additionalDecorIngsLabel.grid(row=0, column = 1)
    #create ingredient combobox 
    additionalDecorIngsCombo = ttk.Combobox(row5Frame, textvariable=tk.StringVar(), width =30, values=[' + New Ingredient'], style = "TCombobox")
    additionalDecorIngsCombo.grid(row=0, column = 2, padx = (39,0))
    additionalDecorIngsCombo.bind('<Button>', enterValue)
    additionalDecorIngsCombo.bind('<<ComboboxSelected>>', checkForModuleChange)
    #create button and link to ingredient combo to search
    searchButton4 = tk.Button(row5Frame, text='Search')
    searchButton4.grid(row=0, column = 3, padx = (3,0))
    searchButton4.bind('<Button>', enterValue)
    searchButton4.bind('<Button>', searchForIngredient)
    pairing[searchButton4] = additionalDecorIngsCombo
    #create critical widgets - clarify button and title below checkbox
    criticalFrame2 = tk.Frame(row5Frame, bg = "#D8D7E8")
    criticalDecorIngs = ttk.Checkbutton(criticalFrame2)
    criticalDecorIngs.grid(row=0, column=0)
    criticalLabel2 = tk.Label(criticalFrame2,  bg = "#D8D7E8", text = 'Critical?')
    criticalLabel2.grid(row=1, column=0)   
    criticalDecorClarifyButton = tk.Button(master=criticalFrame2, command = criticalClarify, text = '?', width = 4, height = 2)
    criticalDecorClarifyButton.grid(row=1, column=1)
    criticalDecorClarifyButton.bind('<Button>', enterValue)
    criticalFrame2.grid(row=0, column = 4, padx = (30,10))
    #create quantity title and entry for ingredient
    quantityLabel2 = tk.Label(master=row5Frame, fg = "#4F2C54", background = "#D8D7E8", text="Quantity", font=("Arial", 15))
    quantityLabel2.grid(row = 0, column = 6, padx = (20,0))
    quantityEntry2 = tk.Entry(row5Frame, width = 10)
    quantityEntry2.grid(row=0, column = 7, padx = 10)
    quantityEntry2.bind('<Button>', enterValue)
    #create add button when pair is entered
    addDecorIngsButton = tk.Button(row5Frame, text='Add', command = checkDecorIng)
    addDecorIngsButton.grid(row=0, column = 8, padx = (20,0))
    row5Frame.place(relx = .02, rely = .52)

    #create and place text for showing added decor ingredients on page 
    global enteredDecorIngsList
    enteredDecorIngsList = []
    global criticalDecorList
    criticalDecorList = []
    enteredDecorIngsListToShow = ', '.join(enteredDecorIngsList)
    global enteredDecorIngsListLabel
    enteredDecorIngsListLabel = tk.Label(master=welcomeWindow, fg = "#4F2C54", background = "#D8D7E8", text=enteredDecorIngsListToShow, font=("Arial", 15), justify = 'center')
    enteredDecorIngsListLabel.place(relx = .5, rely = .62,  anchor='c')

    #create and display widgets for 6th row - packaging
    global quantityEntry3
    row6Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    #create title label 
    packagingLabel = tk.Label(master=row6Frame, fg = "#4F2C54", background = "#D8D7E8", text="Packaging", font=("Arial", 20), justify = 'right')
    packagingLabel.grid(row=0, column = 0)
    #create packaging combobox
    packagingItemCombo = ttk.Combobox(row6Frame, textvariable=tk.StringVar(), width =30, values=[' + New Packaging Item'], style = "TCombobox")
    packagingItemCombo.grid(row=0, column = 1, padx = (39,0))
    packagingItemCombo.bind('<Button>', enterValue)
    packagingItemCombo.bind('<<ComboboxSelected>>', checkForModuleChange)
    #create button and link to packaging combo to search
    searchButton5 = tk.Button(row6Frame, text='Search')
    searchButton5.grid(row=0, column = 2, padx = (3,0))
    searchButton5.bind('<Button>', enterValue)
    searchButton5.bind('<Button>', searchForPackaging)
    pairing[searchButton5] = packagingItemCombo
    #create quantity title and entry for item
    quantityLabel3 = tk.Label(master=row6Frame, fg = "#4F2C54", background = "#D8D7E8", text="Quantity (units)", font=("Arial", 15))
    quantityLabel3.grid(row = 0, column = 3, padx = (20,0))
    quantityEntry3 = tk.Entry(row6Frame, width = 10)
    quantityEntry3.grid(row=0, column = 4, padx = 10)
    quantityEntry3.bind('<Button>', enterValue)
    #create add button when pair is entered
    addPackagingButton = tk.Button(row6Frame, text='Add', command = checkPackagingItem)
    addPackagingButton.grid(row=0, column = 5, padx = (20,0))
    row6Frame.place(relx = .09, rely = .65)

    #create and place text for showing added packaging items on page 
    global enteredPackagingList
    enteredPackagingList = []
    enteredPackagingListToShow = ', '.join(enteredPackagingList)
    global enteredPackagingListLabel
    enteredPackagingListLabel = tk.Label(master=welcomeWindow, fg = "#4F2C54", background = "#D8D7E8", text=enteredPackagingListToShow, font=("Arial", 15), justify = 'center')
    enteredPackagingListLabel.place(relx = .5, rely = .7,  anchor='c')

    #create and display additional notes widgets on page
    row7Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    addNotesLabel = tk.Label(master=row7Frame, fg = "#4F2C54", background = "#D8D7E8", text="Additional" + '\n' + "Notes", font=("Arial", 20), justify = 'right')
    addNotesLabel.grid(row=0, column = 0)
    addNotesEntry = tk.Entry(row7Frame, width = 90)
    addNotesEntry.bind('<Button>', enterValue)
    addNotesEntry.grid(row=0, column = 1, padx = 30)
    row7Frame.place(relx = .09, rely = .74)

    #create and display working hours button to run module
    row8Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    workingHoursLabel = tk.Label(master=row8Frame, fg = "#4F2C54", background = "#D8D7E8", text = "Working Hours", font=("Arial", 20), justify = 'right')
    workingHoursLabel.grid(row=0, column = 0)
    workingHoursButton = tk.Button(row8Frame, width = 30, command = addWorkingHours, text = 'Schedule', highlightbackground = '#C6D8D9' )
    workingHoursButton.bind('<Button>', enterValue)
    workingHoursButton.grid(row=0, column = 1, padx = 30)
    row8Frame.place(relx = .07, rely = .83)

    #create and display button to validate and save user's entries when all fields entered
    row9Frame = tk.Frame(master= welcomeWindow, background = "#D8D7E8")
    confirmButton = tk.Button(row9Frame, width = 10, command = validate, height = 2, text = 'Confirm', highlightbackground = '#C6D8D9' )
    confirmButton.grid(row=0, column = 0, padx = 10)
    #create and display button to cancel recipe entry
    cancelButton = tk.Button(row9Frame, width = 10, height = 2, command = homepage, text = 'Cancel', highlightbackground = '#C6D8D9' )
    cancelButton.grid(row=0, column = 1, padx = 10)
    row9Frame.place(relx = .5, rely = .9, anchor = 'c')

#runs everytime a new page is opened to reset any flags and delete any global variables needed
def changeScreen():
    global previous
    global newWindowFlag
    win = ''
    if previous[len(previous)-1].title() == 'Homepage Window':
        global businessNameEntry
        global businessName
        #fetch business name from widget and save to database
        businessName = businessNameEntry.get()
        if "'" in businessName:
            businessName = businessName.replace("'", "")
        mycursor.execute("UPDATE tblLoginInfo SET BusinessName = '" + businessName + "'")
        mydb.commit()
    if previous[len(previous)-1].title() == 'Add Order Window':
        if newWindowFlag == False:
            global enteredRecipesList
            global enteredPrepIngsList
            global enteredDecorIngsList
            global enteredPackagingList
            #delete all lists of entered items before the page may be used again 
            try:
                del enteredRecipesList
            except:
                pass
            try:
                del enteredPrepIngsList
            except:
                pass
            try:
                del enteredDecorIngsList
            except:
                pass
            try:
                del enteredPackagingList
            except:
                pass
        #remove any closed windows and reset flag
        if len(previous) > 1 and newWindowFlag == False:
            win = previous.pop()
        if len(previous) > 2:
            newWindowFlag = False
    elif previous[len(previous)-1].title() == 'Recipe Window':
        #delete widget array and reset specific flag
        if newWindowFlag == False:
            global ingredientRows
            del ingredientRows
        global newRecipeFlag
        newRecipeFlag = False
        #remove any closed windows and reset flag
        if len(previous) > 1 and newWindowFlag == False:
            win = previous.pop()
        if len(previous) > 2:
            newWindowFlag = False
    elif previous[len(previous)-1].title() == 'Batch Size Window':
        #reset specific flag
        global newBatchFlag
        newBatchFlag = False
        #remove any closed windows and reset flag
        if len(previous) > 1 and newWindowFlag == False:
            win = previous.pop()
        if len(previous) > 2:
            newWindowFlag = False
    elif previous[len(previous)-1].title() == 'Ingredient Window':
        #delete widget array and reset specific flag
        global qtyInStockRows
        del qtyInStockRows
        global newIngredientFlag
        newIngredientFlag = False
        #remove any closed windows and reset flag
        if len(previous) > 1 and newWindowFlag == False:
            win = previous.pop()
        if len(previous) > 2:
            newWindowFlag = False
    elif previous[len(previous)-1].title() == 'Packaging Window':
        #reset specific flag
        global newPackagingFlag
        newPackagingFlag = False
        #remove any closed windows and reset flag
        if len(previous) > 1 and newWindowFlag == False:
            win = previous.pop()
        if len(previous) > 2:
            newWindowFlag = False
    #return the just closed window
    return win


def predictIngredientDemand(ingID, total, shelfLife, timeInterval): #i think this function is dodgy tbh
    #only calulate a predicted quantity if shelf life over 28 days
    if shelfLife < 28:
        print('shelf life under 28 days')
        return total
    else:
        print('shelf life over or equal to 28 days')
        #calculate quantity needed in a week according to time passed in
        avgPerWeekCalc = (total/timeInterval)*7
        #fetch predicted quantity needed in a week from database
        mycursor.execute("SELECT AvgWeeklyDemand FROM tblBaseIngredient WHERE IngredientID = " + str(ingID))
        avgWeeklyDemandPred = mycursor.fetchall()[0][0]
        #check if calculated amount is much less than predicted
        if avgPerWeekCalc > (avgWeeklyDemandPred*0.75):
            #quantity needed is realistic so keep as is
            totalQuantity = total
        else:
            #quantity needed replaced with predicted amount in time
            totalQuantity = math.ceil((avgWeeklyDemandPred/7) * timeInterval)
        return totalQuantity

def createTotalIngQtyDict(quantitiesNeeded1, quantitiesNeeded2):
    totalIngQtyDict = {}
    for usage in quantitiesNeeded1:
        try:
            try:
                shopIDs = totalIngQtyDict[usage[1]].append(usage[2])
                totalIngQtyDict[usage[1]] = [totalIngQtyDict[usage[1][0]] + usage[0], shopIDs]
            except:
                totalIngQtyDict[usage[1]] = [totalIngQtyDict[usage[1]][0] + usage[0], [usage[2]]]
        except:
            try:
                totalIngQtyDict[usage[1]] = [usage[0], [totalIngQtyDict[usage[1]][1] + usage[2]]]
            except:
                totalIngQtyDict[usage[1]] = [usage[0], [usage[2]]]
    for usage in quantitiesNeeded2:
        try:
            try:
                shopIDs = totalIngQtyDict[usage][1].append(usage[2])
                totalIngQtyDict[usage[1]] = [totalIngQtyDict[usage[1]][0] + usage[0], shopIDs]
            except:
                totalIngQtyDict[usage[1]] = [totalIngQtyDict[usage[1]][0] + usage[0], [usage[2]]]
        except:
            try:
                totalIngQtyDict[usage[1]] = [usage[0], [totalIngQtyDict[usage[1]][1 + usage[2]]]]
            except:
                totalIngQtyDict[usage[1]] = [usage[0], [usage[2]]]
    return totalIngQtyDict

def findPurchasableCombos(totalQtyNeeded, ingID):

    #inner function
    def findCombinationsUtil(arr, index, num, reducedNum):
     
        #base condition
        if (reducedNum < 0):
            return
 
        #if combination is found, print it
        if (reducedNum == 0):
            global validAmount
            validAmount = True
            return
    
 
        #find the previous number stored in arr[] - it helps in maintaining increasing order
        if index != len(arr):
            if arr[index] == 0:
                prev = 0
            else:
                prev1 = arr[index-1]
                prev = quantities.index(prev1)
        #replacing next space with numbers only bigger than previous one in arr
        #k is index of previously lowest quantity
        #prev needs to be index in quantities array of previosuly lowest quantity
     
        # note loop starts from previous number i.e. at array location index - 1
        for k in range(prev, len(quantities)):
    
            # next element of array is k
            if index != len(arr):
                arr[index] = quantities[k]
 
            #call recursively with reduced number
            if index != len(arr):
                findCombinationsUtil(arr, index + 1, num, reducedNum - arr[index])

    #outer function
    def findCombinations(n):
     
        # array to store the combinations
        # It can contain max n elements
        arr = [0] * (len(quantities)+1000)
 
        # find all combinations
        findCombinationsUtil(arr, 0, n, n)

    #fetch purchasable quantities for ingredient to combine
    mycursor.execute("SELECT PurchasableQuantity from tblPuchasableQuantity WHERE IngredientID = " + str(ingID))
    records = mycursor.fetchall()
    quantities = []
    for ele in records:
        quantities.append(ele[0])

    #initial execution to increment from quantity needed
    global validAmount
    while validAmount == False:
        findCombinations(totalQtyNeeded)
        totalQtyNeeded += 1
    return totalQtyNeeded-1

def findBestShop(uncoveredList, uncoveredDict, wasteProportionDict, existingOptimalShops, endCoveredShopDate, nextToCoverDate, ingID, shelfLife, covered, uncovered):
    #find all wastes that are an existing shop - if some then check waste is 25% or less worse than best waste, choose lowest waste of them
    #if none then just use lowest waste
    print(uncoveredList)
    newWasteProportionDict = {}
    newFlag = False
    finishKey = ''

    #find which endCovered options allow the next shop after to be on the same date as an existing shop (reducing trips for the user)
    for optimalDate in existingOptimalShops:
        for key in wasteProportionDict: 
            #find endCovered dates of all options
            waste = wasteProportionDict[key]
            date = key[0]
            print('for date option' + str(date))
            try:
                index = uncoveredList.index(key)
                try:
                    #find date of shop AFTER this endCovered 
                    nextDate = uncoveredList[index+1][0]
                    if optimalDate == nextDate:
                        print('the next shop will be on ' + str(nextDate) + ' which matches an existing shop')
                        #next shop is on a date with an existing shop so add to new dictionary
                        newWasteProportionDict[key] = waste
                        newFlag = True
                except:
                    #endCovered has no uncovered shops after  
                    finishKey = key
            except:
                #the date of this option is for the full shelf life not a shop date so find the last shop before it 
                items = [item for item in uncoveredList if item[0] == endCoveredShopDate]
                finalItem = items[(len(items))-1]
                index = uncoveredList.index(finalItem)
                try:
                    #find date of shop AFTER this endCovered 
                    nextDate = uncoveredList[index+1][0]
                    if optimalDate == nextDate:
                        print('the next shop will be on ' + str(nextDate) + ' which matches an existing shop')
                        #next shop is on a date with an existing shop so add to new dictionary
                        newWasteProportionDict[key] = waste
                        newFlag = True
                except:
                    #endCovered has no uncovered shops after  
                    finishKey = key[0]

    if newFlag == True:
        flag = False
        dateToUse = today - timedelta(days=1)
        print('some shops match an existing shop')
        #find lowest waste proportion option out of OLD dictionary
        values = []
        for key in wasteProportionDict:
            value = wasteProportionDict[key]
            values.append(value[1])
        bestWaste = min(values)
        print('lowest waste option of all is ' + str(bestWaste))
        lowest = 1
        #check waste in each NEW option is no more that 25% worse than overall best waste option, choose lowest waste of them
        for key in newWasteProportionDict:
            date = key[0]
            waste = newWasteProportionDict[key][1]
            if waste <= bestWaste*1.25 and waste <= lowest:
                flag = True
                if waste == lowest:
                    #find latest date (more shops covered) with this waste proportion, if any have the same waste proportion
                    if date > dateToUse:
                        lowest = waste
                        dateToUse = date
                        keyToUse = key
                        record = newWasteProportionDict[keyToUse]
                else:
                    #find endCovered date for this best option
                    lowest = waste 
                    dateToUse = date
                    keyToUse = key
                    record = newWasteProportionDict[keyToUse]
        if flag == False:
            #no valid options from NEW dictionary found so use best option from OLD one
            print('no valid options from NEW dictionary found so use best option from OLD one')
            for key in wasteProportionDict:
                value = wasteProportionDict[key]
                if value[1] == bestWaste:
                    keyToUse = key
                    dateToUse = key[0]
                    record = value
            
    else:
        #find lowest waste proportion option out of OLD dictionary (no options that match up with existing shop dates)
        print('no valid options from NEW dictionary found so use best option from OLD one')
        lowest = 1
        for key in wasteProportionDict:
            value = wasteProportionDict[key]
            print(key, value)
            print(value[1])
            if value[1] <= lowest:
                if value[1] == lowest:
                    if key[0] > dateToUse:
                        lowest = value[1]
                        dateToUse = key[0]
                        keyToUse = key
                        record = value
                else:
                    print('here')
                    print(key)
                    keyToUse = key
                    dateToUse = key[0]
                    record = value
                    lowest = value[1]
        if len(uncoveredList) == 1:
            #only this shop uncovered so no more shops left to cover in optimisation for this ingredient
            finishKey = keyToUse
                
    #add best option to file
    if record[0] != 0:
        print('option ' + str(keyToUse) + ' has the lowest waste of valid options so use this option - quantity for list is ' + str(record[0]))
        mycursor.execute("SELECT IngredientName, QuantityUnit from tblBaseIngredient WHERE IngredientID = " + str(ingID))
        record = mycursor.fetchall()[0]
        ingredientName = record[0]
        unit = record[1]
        
        try:
            file = open("ShopList" + str(uncoveredList[0][0]), "r")
            lines = file.readlines()
            newLines = []
            flag = False
            for line in lines:
                if line != '\n':
                    if line.split(': ')[0] != ingredientName:
                        print('here')
                        newLines.append(line)
                    else:
                        oldQtyAndUnit = (line.split(': '))[1]
                        oldQty = float((oldQtyAndUnit.split(unit))[0])
                        newQty = oldQty + float(record[0])
                        newLines.append(ingredientName + ': ' + str(newQty) + str(unit) + "\n")
                        flag = True
            if flag == False:
                newLines.append(ingredientName + ': ' + str(record[0]) + str(unit) + "\n")
            file = open("ShopList" + str(uncoveredList[0][0]), "w")
            for line in newLines:
                file.write(line)
            file.close()
        except:
            file = open("ShopList" + str(uncoveredList[0][0]), "a")
            file.write(ingredientName + ': ' + str(record[0]) + str(unit) + "\n")
            file.close()
            

    #check if any shops still to cover for this ingredient
    finishFlag = False
    if keyToUse != finishKey:
        #still shops to cover - find nextToCover
        try:
            index = uncoveredList.index(keyToUse)
            nextToCoverKey = uncoveredList[index+1]
            prevCoveredKey = uncoveredList[index-1]
            if nextToCoverKey[0] == keyToUse[0] or prevCoveredKey[0] == keyToUse[0]:
                keys = [key for key in uncoveredList if key[0] == keyToUse[0]]
                nextToCoverKey = keys[0]
                
        except:
            #the date of this option is for the full shelf life not a shop date so find the last shop before it 
            items = [item for item in uncoveredList if item[0] == endCoveredShopDate]
            print(items)
            finalItem = items[(len(items)-1)]
            index = uncoveredList.index(finalItem)
            print(uncoveredList)
            try:
                nextToCoverKey = uncoveredList[index+1]
            except:
                finishFlag = True
            
        #add all shops covered by the chosen option to array
        shopIDsToCheck = []
        mycursor.execute("SELECT ShopID FROM tblBaseIngredientInOrder, tblInitialShoppingLists WHERE IngredientID = " + str(ingID) + " and EndDateRequired < '" + str(dateToUse) + "' and tblBaseIngredientInOrder.IngredientUseID = tblInitialShoppingLists.IngredientUseID")
        for shop in mycursor:
            shopIDsToCheck.append(shop[0])
        mycursor.execute("SELECT ShopID FROM tblBatchSizeInOrder, tblIngredientInBatchSize, tblInitialShoppingLists WHERE IngredientID = " + str(ingID) + " and tblIngredientInBatchSize.BatchID = tblBatchSizeInOrder.BatchID and EndDateRequired < '" + str(dateToUse) + "' and tblBatchSizeInOrder.BatchUseID = tblInitialShoppingLists.BatchUseID")
        for shop in mycursor:
            shopIDsToCheck.append(shop[0])
        for i in range (len(uncoveredList)):
            date = uncoveredList[i][0]
            print(shopIDsToCheck)
            if i <= index:
                    #shop is chronologically before endCovered so add shopID to array
                    key = uncoveredList[i]
                    shopID = uncoveredDict[key]
                    if shopID in shopIDsToCheck:
                        covered.append(shopID)
                        print('shop '+ str(shopID) + ' has now been covered')

        print(uncoveredList)
        print(uncoveredDict)
        if finishFlag != True:
            print('next shop to cover is ' + str(nextToCoverKey))
            #reset values to run repeated optimisation from next uncovered shop
            nextToCoverDate = nextToCoverKey[0]
            nextToCoverID = uncoveredDict[nextToCoverKey]
            leftoverStock = record[2]
            optimise2(nextToCoverDate, nextToCoverID, leftoverStock, covered, shelfLife, ingID, uncovered)
        else:
            #no shops left to cover for this ingredient so return for next ingredient
            print('no shops left to cover for this ingredient')
        return
                
        
        
    else:
        #no shops left to cover for this ingredient so return for next ingredient
        print('no shops left to cover for this ingredient')
        return 

#repeating optimisation
def optimise2(nextToCoverDate, nextToCoverID, leftoverStock1, covered, shelfLife, ingID, uncovered):
    wasteProportionDict = {}
    print('entering recursive algorithm')
    #try covering decrementing number of shops from nextToCover - starting with the longest possible (full shelf life)
    endCovered = nextToCoverDate + timedelta(days = shelfLife)
    endCoveredKey = (endCovered, '0')#or check choosing LATEST of same end date  
    expiry = endCovered
    uncoveredDict = {}
    uncoveredList = []
    #remove covered shops from all shops for ingredient to get uncovered shops
    for element in covered:
        try:
            uncovered.remove(element)
        except:
            pass
    #fetch initial shop dates for uncovered shops
    for shopID in uncovered:
        i = 0
        mycursor.execute("SELECT Date FROM tblInitialShoppingDates WHERE ShopID = " + str(shopID) + " ORDER BY Date")
        date = mycursor.fetchall()[0][0]
        flag = False
        #create dictionary of each uncovered initial shopDate (with number in key if multiple on same day)
        for key in sorted(uncoveredDict.keys(), key=lambda x: x[0]):
            if date == key[0]:
                flag = True
        if flag == True:
            i += 1
            key = (date, "{:02d}".format(i))
            uncoveredDict[key] = shopID
        else:
            i = 0
            key = (date, "{:02d}".format(0))
            uncoveredDict[key] = shopID
    #create corresponding list of uncovered dates in order
    for fullKey in sorted(uncoveredDict.keys(), key=lambda x: x[0]):
        uncoveredList.append(fullKey)
    #listIndex = len(uncoveredList) 
    #find the last uncovered initial shop before the expiry (shop + shelfLife)
    closest = timedelta(days = 10000000)
    for endDate in uncoveredDict:
        if endDate[0] <= endCovered and endCovered - endDate[0] <= closest:
            closest = endCovered - endDate[0]
            endCoveredShopID = uncoveredDict[endDate]
            endCoveredShopDate1 = endDate[0]
            endCoveredShopDate = endCoveredShopDate1
            listIndex = (uncoveredList.index(endDate)) + 1 #one above the endcov shop date
    flag = False
    #calculate time interval over which the ingredient will be used if up to this max endCovered date
    interval = (endCovered - nextToCoverDate).days
    print('next shop date will be ' + str(nextToCoverDate) + ', but covering which shops?')
    print('starting with the max amount - up until ' + str(endCovered) + " as this is the shelf life")
    #start covering decrementing number of shops from nextToCover (up to endCovered)
    while endCoveredShopDate >= nextToCoverDate and flag == False:
        #find quantity instances that will be used before current endCovered date
        print(covered)
        print(endCovered)
        mycursor.execute("SELECT Quantity, EndDateRequired, ShopID FROM tblBaseIngredientInOrder, tblInitialShoppingLists WHERE IngredientID = " + str(ingID) + " and tblInitialShoppingLists.IngredientUseID = tblBaseIngredientInOrder.IngredientUseID and EndDateRequired <= '" + str(endCovered) + "' and DateRequired > '" + str(nextToCoverDate) + "'")
        quantities1 = mycursor.fetchall()
        newQuantities1 = []
        for quantity in quantities1:
            if quantity[2] not in covered:
                newQuantities1.append(quantity)
        mycursor.execute("SELECT Quantity, EndDateRequired, ShopID FROM tblBatchSizeInOrder, tblIngredientInBatchSize, tblInitialShoppingLists WHERE IngredientID = " + str(ingID) + " and tblIngredientInBatchSize.BatchID = tblBatchSizeInOrder.BatchID and EndDateRequired <= '" + str(endCovered) + "' and DateRequired > '" + str(nextToCoverDate) + "' and tblBatchSizeInOrder.BatchUseID = tblInitialShoppingLists.BatchUseID")
        quantities2 = mycursor.fetchall()
        newQuantities2 = []
        for quantity in quantities2:
            if quantity[2] not in covered:
                newQuantities2.append(quantity)
        quantitiesNeeded = createTotalIngQtyDict(newQuantities1, newQuantities2)
        #if shop id in covered remove 
        print('the quantities needed in this time (using endcovered) are : ' + str(quantitiesNeeded))
        totalQuantityNeeded = 0
        #calculate if any quantities still need purchasing
        for date in quantitiesNeeded:
            totalQuantityNeeded += quantitiesNeeded[date][0]
        if totalQuantityNeeded != 0:
            print('so total needed is ' + str(totalQuantityNeeded))
            #run prediction to see if the total quantity found (totalQuantityNeeded) is accurate or will likely be more
            newTotal  = predictIngredientDemand(ingID, totalQuantityNeeded, shelfLife, interval)
            print('the more accurate prediction of overall total needed in this time is ' + str(newTotal))
            extra = newTotal - totalQuantityNeeded
            roughExpiry = endCoveredShopDate + ((endCovered-endCoveredShopDate)/2)
            #add the predicted extra quantity that will be used in the time to quantities needed                     
            try:
                quantitiesNeeded[roughExpiry][0] += extra
            except:
                quantitiesNeeded[roughExpiry] = [extra, []]
            #calculate if/how leftover stock can cover required quantity instances
            print('leftover stock is ' + str(leftoverStock1))
            print(quantitiesNeeded)
            leftoverStock, qtysToBuy = currentStockCoverage(leftoverStock1, quantitiesNeeded)
            #calculate total quantity needed after any leftover stock used
            totalQuantityNeeded = 0
            for date in qtysToBuy:
                totalQuantityNeeded += qtysToBuy[date][0]
            global validAmount
            validAmount = False
            if totalQuantityNeeded != 0:
                print('total needed is ' + str(totalQuantityNeeded))
                #calculate purchasable amount and leftover if this amount was purchased
                totalQtyToBuy = findPurchasableCombos(totalQuantityNeeded, ingID)
                print('purchasable amount is ' + str(totalQtyToBuy))
                leftover = totalQtyToBuy - totalQuantityNeeded
                #calculate proportion of leftover that is wasted
                leftoverProportion = leftover/totalQtyToBuy
                print('leftover proportion is ' + str(leftoverProportion*100) + ' % of purchased amount')
                #add purchase waste to overall leftover stock
                totalLeftovers = leftoverStock
                totalLeftovers.append([leftover, expiry])
                #add leftover proportion to waste dictionary for this temporary endCovered date
                wasteProportionDict[endCoveredKey] = (totalQtyToBuy, leftoverProportion, totalLeftovers) 
            else:
                print('total needed is 0, so no leftover')
                totalQtyToBuy = 0
                leftover = 0
                leftoverProportion = 0
                totalLeftovers = leftoverStock
                wasteProportionDict[endCoveredKey] = (totalQtyToBuy, leftoverProportion, totalLeftovers) 
            #reset values to decrement to only cover up to previous shop
            listIndex = listIndex - 1
            if listIndex >= 0:
                print(listIndex)
                print(uncoveredList)# - check here -
                endCoveredKey = uncoveredList[listIndex]
                endCoveredShopDate = uncoveredList[listIndex][0]
                endCovered = endCoveredShopDate
                endCoveredShopID = uncoveredDict[endCoveredKey]
                print('now decrementing to ' + str(endCoveredShopID) + ' on ' + str(endCoveredShopDate))
                print(uncoveredDict)
                interval = (endCovered - nextToCoverDate).days
            else:
                #no more shops to decrement to - choose lowest waste (best) option
                flag = True
        else:
            #no more shops to decrement to -  choose lowest waste (best) option
            flag = True
            
    #no more shops to decrement to

    #fetch any existing optimised shop dates from files (from previous ingredients)
    existingOptimalShops = []
    for fname in os.listdir("."):
        if fname.startswith('ShopList'):
            date = fname[8:]
            existingOptimalShops.append(datetime.strptime(date, "%Y-%m-%d").date())
    print('no more shops to decrement to')
    print('existing optimal shops: ' + str(existingOptimalShops))
    #choose lowest waste (best) option
    print('uncovered dict: '+ str(uncoveredDict))
    print('waste dict: '+ str(wasteProportionDict))
    
    findBestShop(uncoveredList, uncoveredDict, wasteProportionDict, existingOptimalShops, endCoveredShopDate1, nextToCoverDate, ingID, shelfLife, covered, uncovered)      
    

def shoppingOptimisation():
    global quantities
    #delete all optimised shopping lists
    for fname in os.listdir("."):
        if fname.startswith('ShopList'):
            print('deleting shop list file ' + str(fname))
            os.remove(os.path.join(fname))
    #set onListDate for all packaging records as None
    mycursor.execute("UPDATE tblPackagingItems SET OnListDate = 'None'")
    mydb.commit()
    #fetch number of stored initial shops in initialShoppingDates
    mycursor.execute("SELECT ShopID, Date from tblInitialShoppingDates WHERE Date >= '" + str(today) + "'")
    shopIDs = mycursor.fetchall()
    global validAmount
    validAmount = False
    ingsDone = []
    if len(shopIDs) == 1:
        #run algorithm for only one shop
        print('there is only one shop')
        shopID = shopIDs[0][0]
        shopDate = shopIDs[0][1]
        ings = []
        #fetch all additional ingredients in this shop and make list of them
        mycursor.execute("SELECT tblBaseIngredient.IngredientID from tblInitialShoppingLists, tblInitialShoppingDates, tblBaseIngredientInOrder, tblBaseIngredient WHERE tblInitialShoppingDates.ShopID = " + str(shopID) + " and tblInitialShoppingLists.ShopID = tblInitialShoppingDates.ShopID and tblInitialShoppingLists.IngredientUseID = tblBaseIngredientInOrder.IngredientUseID and tblBaseIngredientInOrder.IngredientID = tblBaseIngredient.IngredientID")
        records = mycursor.fetchall()
        for ing in records:
            if ing not in ings:
                ings.append(ing)
        #fetch all ingredients from batches in this shop and make list of them
        mycursor.execute("SELECT tblBaseIngredient.IngredientID from tblInitialShoppingLists, tblInitialShoppingDates, tblBatchSizeInOrder, tblIngredientInBatchSize, tblBaseIngredient WHERE tblInitialShoppingDates.ShopID = " + str(shopID) + " and tblInitialShoppingLists.ShopID = tblInitialShoppingDates.ShopID and tblInitialShoppingLists.BatchUseID = tblBatchSizeInOrder.BatchUseID and tblBatchSizeInOrder.BatchID = tblIngredientInBatchSize.BatchID and tblIngredientInBatchSize.IngredientID = tblBaseIngredient.IngredientID")
        records = mycursor.fetchall()
        for ing in records:
            if ing not in ings:
                ings.append(ing)
        print('these are all the ingredients in this shop: ' + str(ings))
        for ing in ings:
            print('looking at ingredient ' + str(ing[0]))
            #THIS IS ALL JUST FOR CURRENT INGREDIENT
            #find total quantity instances of ingredient needed for all orders
            mycursor.execute("SELECT Quantity, EndDateRequired, ShelfLife from tblBaseIngredientInOrder, tblBaseIngredient WHERE tblBaseIngredient.IngredientID = " + str(ing[0]) + " and tblBaseIngredientInOrder.IngredientID = tblBaseIngredient.IngredientID")
            qtyForAllOrders1 = mycursor.fetchall()
            mycursor.execute("SELECT Quantity, EndDateRequired, ShelfLife from tblBatchSizeInOrder, tblIngredientInBatchSize, tblBaseIngredient WHERE tblBaseIngredient.IngredientID = " + str(ing[0]) + " and tblIngredientInBatchSize.IngredientID = tblBaseIngredient.IngredientID and tblIngredientInBatchSize.BatchID = tblBatchSizeInOrder.BatchID")
            qtyForAllOrders2 = mycursor.fetchall()
            totalIngQtyDict = createTotalIngQtyDict(qtyForAllOrders1, qtyForAllOrders2)
            print('all the ingredients instances and their endDates and shelfLives are: ' + str(totalIngQtyDict))
            #find current stock of ingredient from database
            mycursor.execute("SELECT tblItemsInStock.Quantity, ExpiryDate from tblItemsInStock WHERE tblItemsInStock.IngredientID = " + str(ing[0]) + " ORDER BY ExpiryDate")
            qtysInStock = mycursor.fetchall()
            print('the stock for this ingredient: ' + str(qtysInStock))
            #calculate if/how the current stock can cover the required quantities
            qtysInStock, totalIngQtyDict = currentStockCoverage(qtysInStock, totalIngQtyDict)
            totalQtyNeeded = 0
            #calculate if any quantity instances will still need purchasing
            for dateNeeded in totalIngQtyDict:
                    qtyNeeded = totalIngQtyDict[dateNeeded][0]
                    totalQtyNeeded += qtyNeeded
            #calculate purchasable amount and put on optimised list for same initial shop date 
            if totalQtyNeeded != 0:
                print('some shopping needs doing! total needed is ' + str(totalQtyNeeded))
                validAmount = False
                qtyToAddToList = findPurchasableCombos(totalQtyNeeded, ing[0])
                print('purchasable quantity is ' + str(qtyToAddToList))
                file = open("ShopList" + str(shopDate), "a")
                mycursor.execute("SELECT IngredientName, QuantityUnit from tblBaseIngredient WHERE IngredientID = " + str(ing[0]))
                record = mycursor.fetchall()[0]
                ingredientName = record[0]
                unit = record[1]
                file.write(ingredientName + ": " + str(qtyToAddToList) + str(unit) + "\n")
                file.close()
            else:
                print('no need to purchase')
    else:
        #there is more than one shop planned
        print('there is more than one shop planned')
        ingsAndShops = []
        for shop in shopIDs:
            shopID = shop[0]
            #fetch all additional ingredients in each shop and make list of them
            mycursor.execute("SELECT tblBaseIngredient.IngredientID from tblInitialShoppingLists, tblInitialShoppingDates, tblBaseIngredientInOrder, tblBaseIngredient WHERE tblInitialShoppingDates.ShopID = " + str(shopID) + " and tblInitialShoppingLists.ShopID = tblInitialShoppingDates.ShopID and tblInitialShoppingLists.IngredientUseID = tblBaseIngredientInOrder.IngredientUseID and tblBaseIngredientInOrder.IngredientID = tblBaseIngredient.IngredientID")
            records = mycursor.fetchall()
            for ing in records:
                ingsAndShops.append([ing, shopID])
            #fetch all batch ingredients in each shop and make list of them
            mycursor.execute("SELECT tblBaseIngredient.IngredientID from tblInitialShoppingLists, tblInitialShoppingDates, tblBatchSizeInOrder, tblIngredientInBatchSize, tblBaseIngredient WHERE tblInitialShoppingDates.ShopID = " + str(shopID) + " and tblInitialShoppingLists.ShopID = tblInitialShoppingDates.ShopID and tblInitialShoppingLists.BatchUseID = tblBatchSizeInOrder.BatchUseID and tblBatchSizeInOrder.BatchID = tblIngredientInBatchSize.BatchID and tblIngredientInBatchSize.IngredientID = tblBaseIngredient.IngredientID")
            records = mycursor.fetchall()
            for ing in records:
                ingsAndShops.append([ing, shopID])
        #ALL ingredients and quantities from ALL shops are ingsAndShops
        print('these are all the ingredients and quantities in each shop: ' + str(ingsAndShops))
        #find first initial shop date after current date
        mycursor.execute("SELECT Date, ShopID FROM tblInitialShoppingDates")
        veryFirstShopDate = today + timedelta(days = 2000)
        for shop in mycursor:
            if shop[0] >= today and shop[0] < veryFirstShopDate:
                veryFirstShopDate = shop[0]
                veryFirstShopID = shop[1]
        #set ingredient to first in ingsAndShops array
        shopsForIng = []
        for ing in ingsAndShops:
            ingID = ing[0][0]
            if ingID not in ingsDone:
                print('\n')
                print('looking at '+ str(ingID))
                #find all the shopIDs with this ingredient in
                for record in ingsAndShops:
                    if record[0][0] == ingID:
                        shopsForIng.append(record[1])
                #fetch shelfLife of ingredient from database
                mycursor.execute("SELECT ShelfLife from tblBaseIngredient WHERE IngredientID = " + str(ingID))
                shelfLife = mycursor.fetchall()[0][0]
                print('all the shops with this ingredient in: ' + str(shopsForIng))
                firstShop = today + timedelta(days = 2000)
                for shop in shopsForIng:
                    #find details of each shop for this ingredient
                    mycursor.execute("SELECT Date, ShopID, OrderID FROM tblInitialShoppingDates WHERE ShopID = " + str(shop))
                    record = mycursor.fetchall()[0]
                    shopDate = record[0]
                    shopID = record[1]
                    orderID = record[2]
                    #find first shop for this ingredient after current date 
                    if shopDate >= today and shopDate < firstShop:
                        firstShop = shopDate
                        firstShopID = shopID
                        firstOrderID = orderID
                print('the first shop of these is ' + str(firstShopID) + " " + str(firstShop) + ' for order ' + str(orderID))
                #check if first shop date for this ingredient is the VERY first of all stored shops
                if firstShop == veryFirstShopDate:
                    #find total quantity instances of ingredient needed for ORDER linked to first shop 
                    mycursor.execute("SELECT Quantity, EndDateRequired, ShopID FROM tblBaseIngredientInOrder, tblInitialShoppingLists WHERE OrderID = " + str(firstOrderID) + " and IngredientID = " + str(ingID) + " and tblInitialShoppingLists.IngredientUseID = tblBaseIngredientInOrder.IngredientUseID")
                    qtyForOrder1 = mycursor.fetchall()
                    mycursor.execute("SELECT Quantity, EndDateRequired, ShopID FROM tblBatchSizeInOrder, tblIngredientInBatchSize, tblInitialShoppingLists WHERE OrderID = " + str(firstOrderID) + " and IngredientID = " + str(ingID) + " and tblIngredientInBatchSize.BatchID = tblBatchSizeInOrder.BatchID and tblInitialShoppingLists.BatchUseID = tblBatchSizeInOrder.BatchUseID")
                    qtyForOrder2 = mycursor.fetchall()
                    totalIngQtyDict = createTotalIngQtyDict(qtyForOrder1, qtyForOrder2)
                    print('all the ingredients instances and their endDates are: ' + str(totalIngQtyDict))
                    #find current stock of ingredient from database
                    mycursor.execute("SELECT tblItemsInStock.Quantity, ExpiryDate from tblItemsInStock WHERE tblItemsInStock.IngredientID = " + str(ingID) + " ORDER BY ExpiryDate")
                    qtysInStock = mycursor.fetchall()
                    print('the stock for this ingredient: ' + str(qtysInStock))
                    #find if/how current stock can cover required quantity instances
                    leftoverStock, totalIngQtyDictToBuy = currentStockCoverage(qtysInStock, totalIngQtyDict)
                    totalQtyNeeded = 0
                    #calculate if any quantities still need purchasing 
                    for dateNeeded in totalIngQtyDictToBuy:
                            qtyNeeded = totalIngQtyDictToBuy[dateNeeded][0]
                            totalQtyNeeded += qtyNeeded
                    if totalQtyNeeded != 0:
                        #some shopping needs doing
                        print('some shopping needs doing!')
                        #find the expiry date when the ingredient is purchased on the first stored date
                        endDate = firstShop + timedelta(days=shelfLife)
                        print(' we will see how many shops can be covered in a purchase on ' + str(firstShop) + ' until it expires on ' +  str(endDate))
                        qtyInShelfLife = 0
                        covered = []
                        #fetch additional ingredient quantity instances from all shops that will be used before this expiry date
                        mycursor.execute("SELECT Quantity, ShopID, EndDateRequired FROM tblBaseIngredientInOrder, tblInitialShoppingLists WHERE IngredientID = " + str(ingID) + " and EndDateRequired <= '" + str(endDate) + "' and tblBaseIngredientInOrder.IngredientUseID = tblInitialShoppingLists.IngredientUseID")
                        qtyNeededDict = {}
                        subtraction = 0
                        for qty in mycursor:
                            qtyInShelfLife += qty[0]
                            covered.append(qty[1]) #stores initial shopIDs that can be covered by this shop
                            try:
                                qtyNeededDict[qty[2]][0] += qty[0]
                            except:
                                qtyNeededDict[qty[2]] = [qty[0],[]]
                            subtraction += qty[0]
                        #fetch batch ingredient quantity instances from all shops that will be used before this expiry date
                        mycursor.execute("SELECT Quantity, ShopID, EndDateRequired FROM tblBatchSizeInOrder, tblIngredientInBatchSize, tblInitialShoppingLists WHERE IngredientID = " + str(ingID) + " and tblIngredientInBatchSize.BatchID = tblBatchSizeInOrder.BatchID and EndDateRequired <= '" + str(endDate) + "' and tblBatchSizeInOrder.BatchUseID = tblInitialShoppingLists.BatchUseID")
                        for qty in mycursor:
                            qtyInShelfLife += qty[0]
                            covered.append(qty[1])
                            try:
                                qtyNeededDict[qty[2]][0] += qty[0]
                            except:
                                qtyNeededDict[qty[2]] = [qty[0],[]]
                            subtraction += qty[0]
                        #run prediction to see if the total quantity found (qtyInShelfLife) is accurate or will likely be more
                        qtyInShelfLife = predictIngredientDemand(ingID, qtyInShelfLife, shelfLife, shelfLife)
                        print('the total quantity needed in this time is ' + str(qtyInShelfLife))
                        #add the predicted extra quantity that will be used in the time to quantities needed 
                        qtyNeededDict[endDate] = [qtyInShelfLife-subtraction, []]
                        #calculate if/how current stock can cover required quantity instances
                        leftoverStock, qtyNeeded = currentStockCoverage(qtysInStock, qtyNeededDict)
                        print('the quantity needed after using some current stock in this time is ' + str(qtyNeeded))
                        totalQtyNeeded = 0
                        #calculate if any quantities still need purchasing 
                        for dateNeeded in qtyNeeded:
                            totalQtyNeeded += qtyNeeded[dateNeeded][0]
                        if totalQtyNeeded != 0:
                            #should always run this branch since stock will not cover all quantities needed
                            print('the current stock does not cover '+ str(totalQtyNeeded))
                            #calculate purchasable amount and put on optimised list for same initial shop date 
                            qtyToAddToList = findPurchasableCombos(totalQtyNeeded, ingID)
                            file = open("ShopList" + str(firstShop), "a")
                            mycursor.execute("SELECT IngredientName from tblBaseIngredient WHERE IngredientID = " + str(ingID))
                            ingredientName = mycursor.fetchall()[0][0]
                            file.write(ingredientName + ": " + str(qtyToAddToList) + "\n")
                            file.close()
                            print('so ' + str(qtyToAddToList) + ' is added to a list for ' + str(firstShop))
                            print('this covers shops ' + str(covered))
                            print('all the shops with this ingredient in are ' + str(shopsForIng))
                            #find which shops for this ingredient are still uncovered after this shop
                            uncovered = []
                            for shop in shopsForIng:
                                if shop not in covered:
                                    uncovered.append(shop)
                            nextToCoverDate = today + timedelta(days = 2000)
                            for shop in uncovered:
                                mycursor.execute("SELECT Date FROM tblInitialShoppingDates WHERE ShopID = " + str(shop))
                                shopDate = mycursor.fetchall()[0][0]
                                if shopDate >= today and shopDate < nextToCoverDate:
                                    nextToCoverDate = shopDate
                                    nextToCoverID = shop
                            #check if any more shops to cover for this ingredient
                            if nextToCoverDate == (today + timedelta(days = 2000)):
                                #no more to cover - next ingredient
                                nextToCoverDate = None
                                nextToCoverID = None 
                                print('so the first shop chronologically that still needs covering is ' + str(nextToCoverID))
                            else:
                                #there are more shops to cover - run the repeating optimisation process until done 
                                print('so the first shop chronologically that still needs covering is ' + str(nextToCoverID) + str(nextToCoverDate))
                                optimise2(nextToCoverDate, nextToCoverID, [], covered, shelfLife, ingID, uncovered)
                        else:
                            print("this bit should never run so if it does there's an issue")
                    else:
                        #no shopping needs doing 
                        print('no shopping needs doing for this order')
                        #create array of shopIDs that can be fully covered by current stock
                        covered = []
                        for dateNeeded in totalIngQtyDictToBuy:
                            covered.extend(totalIngQtyDictToBuy[dateNeeded][1])
                        print('current stock covers shops ' + str(covered))
                        print('all the shops with this ingredient in are ' + str(shopsForIng))
                        #create array of shopIDs that are not covered by stock
                        uncovered = []
                        for shop in shopsForIng:
                            if shop not in covered:
                                uncovered.append(shop)
                        #find which uncovered shop is next in time after the final covered one
                        nextToCoverDate = today + timedelta(days = 2000)
                        for shop in uncovered:
                            mycursor.execute("SELECT Date FROM tblInitialShoppingDates WHERE ShopID = " + str(shop) + ' ORDER BY Date')
                            shopDate = mycursor.fetchall()[0][0]
                            if shopDate >= today and shopDate < nextToCoverDate:
                                nextToCoverID = shop
                                nextToCoverDate = shopDate
                        #check if any more shops to cover for this ingredient
                        if nextToCoverDate == today + timedelta(days = 2000):
                            #no more to cover - next ingredient
                            nextToCoverDate = None
                            print('so the first shop chronologically that still needs covering is ' + str(nextToCoverID))
                        else:
                            #there are more shops to cover - run the repeating optimisation process until done 
                            print('so the first shop chronologically that still needs covering is ' + str(nextToCoverID))
                            optimise2(nextToCoverDate, nextToCoverID, leftoverStock, covered, shelfLife, ingID, uncovered)
                            
                        
                else:
                    #not first shop, so initialise shops values and run repeating optimisation process immediately
                    covered = []
                    uncovered = shopsForIng
                    #set shop to cover from as the first one found
                    nextToCoverDate = firstShop
                    nextToCoverID = firstShopID
                    print('first shop to cover is ' + str(nextToCoverID) + ' on ' + str(nextToCoverDate))
                    #fetch current stock of ingredient to use as 'leftover'
                    mycursor.execute("SELECT tblItemsInStock.Quantity, ExpiryDate from tblItemsInStock WHERE ExpiryDate >= '" + str(nextToCoverDate) + "' and tblItemsInStock.IngredientID = " + str(ingID) + " ORDER BY ExpiryDate")
                    leftoverStock = mycursor.fetchall()
                    print('stock before ' + str(nextToCoverDate) + ' is ' + str(leftoverStock))
                    leftoverStock = [list(ele) for ele in leftoverStock]
                    #run repeating optimisation
                    optimise2(nextToCoverDate, nextToCoverID, leftoverStock, covered, shelfLife, ingID, uncovered)            
                    
                validAmount = False
                print('\n')

            #reset for next ingredient
            ingsDone.append(ingID)
            shopsForIng = []


    packagingRestockAll(today)


#called after changes in stored orders to schedule initial shopping dates in database before optimising
def initialShopDateScheduling(orderID):

    #formats a working slot from database entry to datetime object
    def slotToTime(slot):
        date = slot[0]
        time = (datetime.min + slot[1]).time()
        dateTime = datetime.combine(date, time)
        return dateTime

    #finds the closest slot date from array after a given date
    def findClosestSlot(slots, shopDate):
        closest = 10000000
        for slotName in slots:
            #create date format from slot
            shopDate = datetime.combine(shopDate, datetime.min.time())
            slot = slotToTime(slotName)
            #calculate time between slot and given date in minutes
            diff = slot - shopDate
            total_seconds = diff.total_seconds()
            diff = total_seconds / 60 
            if slot >= shopDate and diff < closest:
                #store any closer slot as closest
                closest = diff
                firstSlotTime = slot
        try:
            return firstSlotTime
        except:
            return None
            

    #replaces any date passed in before today's date, to today's date
    def checkShopDate(date):
        if date < datetime.now():
            date = datetime.now()
        return date

    #adds given ingredient to given shop in database tables
    def addIngToDB(ing, shopID, date, endDate):
        ingUseID = ing[1]
        mycursor.execute("INSERT INTO tblInitialShoppingLists (ShopID, IngredientUseID) VALUES (" + str(shopID) + ", " + str(ingUseID) + ")")
        mycursor.execute("UPDATE tblBaseIngredientInOrder SET DateRequired = '" + str(date) + "', EndDateRequired = '" + str(endDate) + "' WHERE IngredientUseID = " + str(ingUseID))                      
        mydb.commit()

    #adds given batch to given shop in database tables
    def addBatchToDB(batch, shopID, date, endDate):
        mycursor.execute("INSERT INTO tblInitialShoppingLists (ShopID, BatchUseID) VALUES (" + str(shopID) + ", " + str(batch) + ")")
        mycursor.execute("UPDATE tblBatchSizeInOrder SET DateRequired = '" + str(date) + "', EndDateRequired = '" + str(endDate) + "' WHERE BatchUseID = " + str(batch))                      
        mydb.commit()

    print('For order ' + str(orderID))
    mycursor.execute("SELECT ShopID FROM tblInitialShoppingDates WHERE OrderID = " + str(orderID))
    shops = mycursor.fetchall()
    for shop in shops:
        print('Deleting shop ' + str(shop[0]))
        mycursor.execute("DELETE FROM tblInitialShoppingLists WHERE ShopID = " + str(shop[0]))
        mycursor.execute("DELETE FROM tblInitialShoppingDates WHERE ShopID = " + str(shop[0]))

    #fetch critical ingredients for order from database
    mycursor.execute("SELECT ShelfLife, IngredientUseID, IngredientType from tblBaseIngredientInOrder, tblBaseIngredient WHERE OrderID = " + str(orderID) + " AND Critical = True AND tblBaseIngredient.IngredientID = tblBaseIngredientInOrder.IngredientID")
    criticalIngs = mycursor.fetchall()
    print('critical ingredients in this order: ' + str(criticalIngs))
    #fetch non-critical decor ingredients for order from database
    mycursor.execute("SELECT ShelfLife, IngredientUseID from tblBaseIngredientInOrder, tblBaseIngredient WHERE OrderID = " + str(orderID) + " AND Critical = False AND IngredientType = 'DECOR' AND tblBaseIngredient.IngredientID = tblBaseIngredientInOrder.IngredientID")
    decorIngs = mycursor.fetchall()
    print('decor ingredient shelf lives and uses in this order: ' + str(decorIngs))
    prepIngs = []
    nonBatchPrepIngs = []
    batches = []
    #fetch prep ingredients WITHIN batch sizes for order from database
    mycursor.execute("SELECT ShelfLife, BatchUseID from tblBatchSizeInOrder, tblIngredientInBatchSize, tblBaseIngredient WHERE OrderID = " + str(orderID) + " AND tblBatchSizeInOrder.BatchID = tblIngredientInBatchSize.BatchID AND tblIngredientInBatchSize.IngredientID = tblBaseIngredient.IngredientID")
    for ing in mycursor.fetchall():
        prepIngs.append(ing)
        if ing[1] not in batches:
            batches.append(ing[1])
    print('batch uses in this order: ' + str(batches))
    #fetch non-critical prep ingredients for order from database
    mycursor.execute("SELECT ShelfLife, IngredientUseID from tblBaseIngredientInOrder, tblBaseIngredient WHERE OrderID = " + str(orderID) + " AND Critical = False AND IngredientType = 'PREP' AND tblBaseIngredient.IngredientID = tblBaseIngredientInOrder.IngredientID")
    records = mycursor.fetchall()
    for ing in records:
        prepIngs.append(ing)
        nonBatchPrepIngs.append(ing)
    print('additional prep ingredient shelf lives and uses in this order: ' + str(nonBatchPrepIngs))
    print('prep ingredient shelf lives and uses INCLUDING batches in this order: ' + str(prepIngs))
    #fetch all PREP working date slots (start times) for order from database
    mycursor.execute("SELECT Date, StartTime from tblWorkingDateSlot WHERE OrderID = " + str(orderID) + " AND SlotType = 'PREP' ")
    prepStarts = mycursor.fetchall()
    #format first slot fetched and set as initial comparison variable
    prepStart1 = slotToTime(prepStarts[0])
    prepEnd1 = slotToTime(prepStarts[0])
    for prepSlot in prepStarts:
        prepStart = slotToTime(prepSlot)
        prepEnd = slotToTime(prepSlot)
        #find slot starting earliest
        if prepStart < prepStart1:
            prepStart1 = prepStart
        #find slot starting latest
        elif prepEnd > prepEnd1:
            prepEnd1 = prepEnd
    print('first prep slot is ' + str(prepStart1))
    print('last prep slot is ' + str(prepEnd1))
    #fetch all DECOR working date slots (end times) for order from database
    mycursor.execute("SELECT Date, EndTime from tblWorkingDateSlot WHERE OrderID = " + str(orderID) + " AND SlotType = 'DECOR' ")
    decorEnds = mycursor.fetchall()
    #format first slot fetched and set as initial comparison variable
    decorStart1 = slotToTime(decorEnds[0])
    decorEnd1 = slotToTime(decorEnds[0])
    for decorSlot in decorEnds:
        decorEnd = slotToTime(decorSlot)
        decorStart = slotToTime(decorSlot)
        #find slot starting latest
        if decorEnd > decorEnd1:
            decorEnd1 = decorEnd
        #find slot starting earliest
        elif decorStart < decorStart1:
            decorStart1 = decorStart
    print('first decor slot is ' + str(decorStart1))
    print('last decor slot is ' + str(decorEnd1))
    #check if need to follow processing for including critical ingredients or not
    if len(criticalIngs) == 0:
        print('no critical ingredients')
        #no critical ingredients so full time is time between first and last slot (hours)
        fullMakeTime = decorEnd1 - prepStart1
        total_seconds = fullMakeTime.total_seconds()
        fullMakeTime = total_seconds / 3600
        print('Full make time is ' + str(fullMakeTime) + ' hours')
        #initialise arbitrary shortest shelf life then find shortest of ALL prep/decor ingredients
        shortestShelfLife = 10000
        for ing in prepIngs:
            if ing[0] < shortestShelfLife:
                shortestShelfLife = ing[0]
        for ing in decorIngs:
            if ing[0] < shortestShelfLife:
                shortestShelfLife = ing[0]
        print('Shortest shelf life of all ingredients ' + str(shortestShelfLife) + ' days')
        #check if will need one or more shops within order's making time
        if shortestShelfLife*24 <= fullMakeTime:
            print('Ingredient(s) will expire so need 2 shops')
            #the shopping will need to be split to ensure ingredients stay in date
            #set prep shop date the day before first prep slot
            prepShoppingDate = checkShopDate(prepStart1 - timedelta(days=1))
            print('Prep shop will be on ' + str(prepShoppingDate))
            #set decor shop date the day before first decor slot            
            decorShoppingDate = checkShopDate(decorStart1 - timedelta(days=1))
            print('Decor shop will be on ' + str(decorShoppingDate))
            #insert prep shop date into database and find ID
            mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(prepShoppingDate) + "')")
            mydb.commit()
            mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(prepShoppingDate.date()) + "'")
            prepShopID = mycursor.fetchall()[0][0]
            #insert decor shop date into database and find ID
            mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(decorShoppingDate) + "')")
            mydb.commit()
            mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(decorShoppingDate.date()) + "'")
            decorShopID = mycursor.fetchall()[0][0]
            print('Shop dates added to database')
            #add non critical decor ingredients to decor shop in database
            for ing in decorIngs:
                addIngToDB(ing, decorShopID, decorStart1, decorEnd1)
                print('Decor ingredient '+str(ing[1]) + ' added to database for shop '+ str(decorShopID))
                print('It must be purchased by ' + str(decorStart1) + ' and not expire until ' + str(decorEnd1))
            #add recipe batches to prep shop in database
            for batch in batches:
                addBatchToDB(batch, prepShopID, prepStart1, prepEnd1)
                print('Batch '+ str(batch) + ' added to database for shop '+ str(prepShopID))
                print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))
            #add non critical prep ingredients to prep shop in database
            for ing in nonBatchPrepIngs:
                addIngToDB(ing, prepShopID, prepStart1, prepEnd1)
                print('Prep ingredient '+ str(ing[1]) + ' added to database for shop '+ str(prepShopID))
                print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))
                
        else:
            print('No ingredients will expire in time so can do one shop')
            #the shopping can all be done on one date - before first prep slot
            shoppingDate = checkShopDate(prepStart1 - timedelta(days=1))
            print('Shop will be on ' + str(shoppingDate.date()))
            #insert shop date into database and find ID
            mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(shoppingDate) + "')")
            mydb.commit()
            mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(shoppingDate.date()) + "'")
            shopID = mycursor.fetchall()[0][0]
            print('Shop dates added to database = ID is ' + str(shopID))
            #add non critical decor ingredients to shop in database
            for ing in decorIngs:
                addIngToDB(ing, shopID, decorStart1, decorEnd1)
                print('Decor ingredient '+ str(ing[1]) + ' added to database for shop '+ str(shopID))
                print('It must be purchased by ' + str(decorStart1) + ' and not expire until ' + str(decorEnd1))
            #add recipe batches to shop in database
            for batch in batches:
                addBatchToDB(batch, shopID, prepStart1, prepEnd1)
                print('Batch '+ str(batch) + ' added to database for shop '+ str(shopID))
                print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))
            #add non critical prep ingredients to shop in database
            for ing in nonBatchPrepIngs:
                addIngToDB(ing, shopID, prepStart1, prepEnd1)
                print('Prep ingredient '+ str(ing[1]) + ' added to database for shop '+ str(shopID))
                print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))
    else:
        print('At least one critical ingredient in order')
        #there are critical ingredients
        #fetch order date from database
        mycursor.execute("SELECT OrderDate from tblCustomerOrder WHERE OrderID = " + str(orderID))
        orderDate = mycursor.fetchall()[0][0]
        print('Order date is ' + str(orderDate) + ' so must not expire before then')
        #calculate full make time between first prep slot and order collection date in hours
        fullMakeTime = orderDate - prepStart1.date()
        total_seconds = fullMakeTime.total_seconds()
        fullMakeTime = total_seconds / 3600
        print('Full make time is ' + str(fullMakeTime) + ' hours')
        #initialise arbitrary shortest shelf life then find shortest of critical ingredients
        shortestShelfLife = 10000
        for ing in criticalIngs:
            if ing[0] < shortestShelfLife:
                shortestShelfLife = ing[0]
        print('Shortest shelf life of critical ingredients ' + str(shortestShelfLife) + ' days')
        #check if will need one or more shops within order's making time
        if shortestShelfLife*24 <= fullMakeTime:
            print('Ingredient(s) will expire so needat least 2 shops')
            #the shopping will need to be split to ensure ingredients stay in date
            #set prep shop date the day before first prep slot
            prepShoppingDate = checkShopDate(prepStart1 - timedelta(days=1))
            #set decor shop date the day before first decor slot            
            decorShoppingDate = checkShopDate(decorStart1 - timedelta(days=1))
            print('Prep shop will be on ' + str(prepShoppingDate))
            print('Decor shop will be on ' + str(decorShoppingDate))
            #insert prep shop date into database and find ID
            mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(prepShoppingDate) + "')")
            mydb.commit()
            mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(prepShoppingDate.date()) + "'")
            prepShopID = mycursor.fetchall()[0][0]
            #insert decor shop date into database and find ID
            mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(decorShoppingDate) + "')")
            mydb.commit()
            mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(decorShoppingDate.date()) + "'")
            decorShopID = mycursor.fetchall()[0][0]
            print('Shop dates added to database')
            #add non critical decor ingredients to decor shop in database
            for ing in decorIngs:
                addIngToDB(ing, decorShopID, decorStart1, decorEnd1)
                print('Decor ingredient '+ str(ing[1]) + ' added to database for shop '+ str(decorShopID))
                print('It must be purchased by ' + str(decorStart1) + ' and not expire until ' + str(decorEnd1))
            #add non critical prep ingredients to prep shop in database
            for ing in nonBatchPrepIngs:
                 addIngToDB(ing, prepShopID, prepStart1, prepEnd1)
                 print('Prep ingredient '+ str(ing[1]) + ' added to database for shop '+ str(prepShopID))
                 print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))
                 
                 
            #add recipe batches to prep shop in database
            for batch in batches:
                addBatchToDB(batch, prepShopID, prepStart1, prepEnd1)
                print('Batch '+ str(batch) + ' added to database for shop '+ str(prepShopID))
                print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))

            #calculate critical decor time as time between order date and first decor slot in hours
            criticalDecorTime = orderDate - decorStart1.date()
            total_seconds = criticalDecorTime.total_seconds()
            criticalDecorTime = total_seconds / 3600
            print('Critical decor time (between start of decor slots and collection) is ' + str(criticalDecorTime) + ' hours')
            lateDecorCriticals = []
            #check if any critical decor ingredients have a shorter shelf life than this time (need to be purchased closer to end)
            for ing in criticalIngs:
                if ing[2] == 'DECOR' and ing[0]*24 < criticalDecorTime:
                    print(str(ing[1]) + ' will expire if purchased before first decor slot')
                    lateDecorCriticals.append(ing)
                elif ing[2] == 'DECOR':
                    #put these in the normal decor shop
                    addIngToDB(ing, decorShopID, decorStart1, orderDate)
                    print(str(ing[1]) + ' will NOT expire if purchased before first decor slot - Added to shop ' + str(decorShopID))
                    print('It must be purchased by ' + str(decorStart1) + ' and not expire until ' + str(orderDate))

            #calculate critical prep time as time between order date and first pre slot in hours
            criticalPrepTime = orderDate - prepStart1.date()
            total_seconds = criticalPrepTime.total_seconds()
            criticalPrepTime = total_seconds / 3600
            print('Critical prep time (between start of prep slots and collection) is ' + str(criticalPrepTime) + ' hours')
            latePrepCriticals = []
            #check if any critical prep ingredients have a shorter shelf life than this time (need to be purchased closer to end)
            for ing in criticalIngs:
                if ing[0]*24 < criticalPrepTime and ing[2] == 'PREP':
                    print(str(ing[1]) + ' will expire if purchased before first prep slot')
                    latePrepCriticals.append(ing)
                elif ing[2] == 'PREP':
                    #put these in the normal prep shop
                    addIngToDB(ing, prepShopID, prepStart1, orderDate)
                    print(str(ing[1]) + ' will NOT expire if purchased before first prep slot - Added to shop ' + str(prepShopID))
                    print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(orderDate))

                    
            #calculate shop date for any critical decor ingredients
            if len(lateDecorCriticals) > 0:
                shortestDecorShelfLife = 10000
                #find shortest shelf life of all these ingredients
                for ing in lateDecorCriticals:
                    if ing[0] < shortestDecorShelfLife:
                        shortestDecorShelfLife = ing[0]
                print('Shortest decor critical shelf life is ' + str(shortestDecorShelfLife))
                #set shop date as earliest the most perishable of these ingredients can be purchased and stay in date
                criticalDecorShoppingDate = orderDate - timedelta(days=shortestDecorShelfLife)
                print('Shop for these late decor criticals is ' + str(criticalDecorShoppingDate))
                #find first decor slot after this shop 
                firstSlotTime = findClosestSlot(decorEnds, criticalDecorShoppingDate)
                if firstSlotTime == None:
                     firstSlotTime = orderDate
                    

                #insert critical decor shop date into database and find ID
                mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(criticalDecorShoppingDate) + "')")
                mydb.commit()
                mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(criticalDecorShoppingDate) + "'")
                criticalDecorShopID = mycursor.fetchall()[0][0]
                print('Shop date added to database = Shop ID is ' + str(criticalDecorShopID))
                #add these late critical decor ingredients to late critical decor shop in database
                for ing in lateDecorCriticals:
                    addIngToDB(ing, criticalDecorShopID, firstSlotTime, orderDate)
                    print('Decor ingredient '+ str(ing[1]) + ' added to database for shop '+ str(criticalDecorShopID))
                    print('It must be purchased by first slot after it on ' + str(firstSlotTime) + ' and not expire until ' + str(orderDate))
            
            if len(latePrepCriticals) > 0:
                newShopFlag = True
                shortestPrepShelfLife = 10000
                #find shortest shelf life of all these ingredients
                for ing in latePrepCriticals:
                    if ing[0] < shortestPrepShelfLife:
                        shortestPrepShelfLife = ing[0]
                print('Shortest prep critical shelf life is ' + str(shortestPrepShelfLife))
                #check if any prep slots are after the decor shop so the late prep ingredients can be added to this existing shop
                if decorShoppingDate.date() >= (orderDate - timedelta(days=shortestPrepShelfLife)):
                    print('Decor shop on ' + str(decorShoppingDate) + ' is not too early') 
                    #ingredient will not expire
                    for slot in prepStarts:
                        prepSlot = slotToTime(slot)
                        try:
                            if prepSlot >= (decorShoppingDate + timedelta(hours=12)):
                                print('There is a prep slot on ' + str(prepSlot) + ' so this shop can be used')
                                #prep slot found after - this shop can be used
                                newShopFlag = False
                                criticalPrepShopID = decorShopID
                                firstSlotTime2 = findClosestSlot(prepStarts, decorShoppingDate)
                        except:
                            newShopFlag = True
                            
                #check if any prep slots are after the critical decor shop so the late prep ingredients can be added to this existing shop
                try: 
                    if criticalDecorShoppingDate >= (orderDate - timedelta(days=shortestPrepShelfLife)):
                        print('Critical decor shop on ' + str(criticalDecorShoppingDate) + ' is not too early') 
                        #ingredient will not expire
                        for slot in prepStarts:
                            prepSlot = slotToTime(slot)
                            if prepSlot >= (criticalDecorShoppingDate + timedelta(hours=12)):
                                print('There is a prep slot on ' + str(prepSlot) + ' so this shop can be used')
                                #prep slot found after - this shop can be used
                                newShopFlag = False
                                criticalPrepShopID = criticalDecorShopID
                                firstSlotTime2 = findClosestSlot(prepStarts, criticalDecorShoppingDate)
                except:
                    newShopFlag = True
                            
                #if no previous shop can be used, add new one
                if newShopFlag == True:
                    print('No decor shops can be used for late prep criticals, add a new shop')
                    #set shop date as earliest the most perishable of these ingredients can be purchased and stay in date
                    criticalPrepShoppingDate = orderDate - timedelta(days=shortestPrepShelfLife)
                    print('Shop for these late prep criticals is ' + str(criticalPrepShoppingDate))
                    #insert critical prep shop date into database and find ID
                    mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(criticalPrepShoppingDate) + "')")
                    mydb.commit()
                    mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(criticalPrepShoppingDate) + "'")
                    criticalPrepShopID = mycursor.fetchall()[0][0]
                    print('Shop date added to database = Shop ID is ' + str(criticalPrepShopID))
                    #find first decor slot after this shop 
                    firstSlotTime2 = findClosestSlot(prepStarts, criticalPrepShoppingDate)
                    
                #add these late critical prep ingredients to late critical decor shop in database
                if firstSlotTime2 == None:
                     firstSlotTime2 = orderDate
                for ing in latePrepCriticals:
                    addIngToDB(ing, criticalPrepShopID, firstSlotTime2, orderDate)
                    print('Prep ingredient '+ str(ing[1]) + ' added to database for shop '+ str(criticalPrepShopID))
                    print('It must be purchased by first slot after it on ' + str(firstSlotTime2) + ' and not expire until ' + str(orderDate))
                
        else:
            print('No ingredients will expire in time so can do one shop')
            #the shopping can all be done on one date - before first prep slot
            shoppingDate = checkShopDate(prepStart1 - timedelta(days=1))
            print('Shop will be on ' + str(shoppingDate.date()))
            #insert shop date into database and find ID
            mycursor.execute("INSERT INTO tblInitialShoppingDates (OrderID, Date) VALUES (" + str(orderID) + ", '" + str(shoppingDate) + "')")
            mydb.commit()
            mycursor.execute("SELECT ShopID from tblInitialShoppingDates WHERE OrderID = " + str(orderID) + " AND Date =  '" + str(shoppingDate.date()) + "'")
            shopID = mycursor.fetchall()[0][0]
            print('Shop dates added to database = ID is ' + str(shopID))
            #add non critical decor ingredients to shop in database
            for ing in decorIngs:
                addIngToDB(ing, shopID, decorStart1, decorEnd1)
                print('Decor ingredient '+ str(ing[1]) + ' added to database for shop '+ str(shopID))
                print('It must be purchased by ' + str(decorStart1) + ' and not expire until ' + str(decorEnd1))
            #add recipe batches to shop in database
            for batch in batches:
                addBatchToDB(batch, shopID, prepStart1, prepEnd1)
                print('Batch '+ str(batch) + ' added to database for shop '+ str(shopID))
                print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))
            #add non critical prep ingredients to shop in database
            for ing in nonBatchPrepIngs:
                addIngToDB(ing, shopID, prepStart1, prepEnd1)
                print('Prep ingredient '+ str(ing[1]) + ' added to database for shop '+ str(shopID))
                print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(prepEnd1))
            for ing in criticalIngs:
                if ing[2] == 'PREP':
                    #add critical prep ingredients to shop in database
                    addIngToDB(ing, shopID, prepStart1, orderDate)
                    print('Critical prep ingredient '+ str(ing[1]) + ' added to database for shop '+ str(shopID))
                    print('It must be purchased by ' + str(prepStart1) + ' and not expire until ' + str(orderDate))
                else:
                    #add critical decor ingredients to shop in database
                    addIngToDB(ing, shopID, decorStart1, orderDate)
                    print('Critical decor ingredient '+ str(ing[1]) + ' added to database for shop '+ str(shopID))
                    print('It must be purchased by ' + str(decorStart1) + ' and not expire until ' + str(orderDate))
        

#initialise all global flags and data structures
global newWindowFlag
newWindowFlag = False
global newRecipeFlag
newRecipeFlag = False
global newIngredientFlag
newIngredientFlag = False
global newBatchFlag
newBatchFlag = False
global newPackagingFlag
newPackagingFlag = False
global batchAdded
batchAdded = False
global newAccountPopup
newAccountPopup = False
global infoButtonMessage
infoButtonMessage = 'homepage'
global tempSlots
tempSlots = []
global pairing
pairing = {}

#create main application window, name and add as previously opened
global welcomeWindow
welcomeWindow = tk.Tk()
welcomeWindow.title("Registration Login Window")
global previous
previous = [welcomeWindow]

#open images from local stored folder, format and save
global arrowIconRight
arrowIconRight = Image.open("ScheduleArrowRight.png")
arrowIconRight = arrowIconRight.resize((40,40))
arrowIconRight = ImageTk.PhotoImage(arrowIconRight)
global arrowIconLeft
arrowIconLeft = Image.open("ScheduleArrowLeft.png")
arrowIconLeft = arrowIconLeft.resize((40,40))
arrowIconLeft = ImageTk.PhotoImage(arrowIconLeft)

#create logout and help buttons, and title widget in main window
global logOutButtonBorder
logOutButtonBorder = tk.Frame(master=welcomeWindow, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
global logOutButton
logOutButton = tk.Button(master=logOutButtonBorder, command = registration_login, justify = 'center', text = '-->', width = 7, height = 4)
logOutButton.pack()
global title
title = tk.Label(master=welcomeWindow, fg = "#4F2C54", bg = "#D8D7E8", text="", font=("Courier", 80))
global infoButtonBorder
infoButtonBorder = tk.Frame(master=welcomeWindow, highlightbackground = "#273A36", highlightthickness = 2, bd=0)
global infoButton
infoButton = tk.Button(master=infoButtonBorder, text = "?", width = 2, font = ("Arial", 50),highlightbackground = '#C6D8D9', command = infoPopup)
infoButton.pack()

#set style for combobox widgets
style= ttk.Style()
style.theme_use('clam')
style.configure("TCombobox", arrowcolor = '#4F2C54')
style.configure("TCheckbutton", background = "#D8D7E8")
checkbuttonStyle = ttk

#display main window and run registration/login page to start application
welcomeWindow.configure(background = "#D8D7E8")
welcomeWindow.attributes('-fullscreen', True)
registration_login()
welcomeWindow.mainloop()
