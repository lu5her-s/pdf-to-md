#!/usr/bin/env python3
"""Generate complex Thai PDF for testing pdf_to_md CLI."""

from fpdf import FPDF
from pathlib import Path

FONT_PATH = "/usr/share/fonts/ttf/Sarabun-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/ttf/Sarabun-Bold.ttf"
OUTPUT = Path("/home/lu5her/00-Inbox/pdf-to-md/test_input_thai.pdf")


class ThaiPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("Thai", "", FONT_PATH)
        self.add_font("Thai", "B", FONT_BOLD)
        self.total_pages = 5

    def header(self):
        self.set_font("Thai", "B", 8)
        self.set_text_color(80, 80, 80)
        self.cell(
            0, 6,
            "รายงานวิเคราะห์ตลาดการลงทุน ประจำไตรมาส 2/2569 | บริษัทหลักทรัพย์จัดการลงทุน จำกัด (มหาชน)",
            align="C",
        )
        self.ln(8)
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font("Thai", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 6,
            f"หน้าที่ {self.page_no()} / ทั้งหมด {self.total_pages} | ความลับภายใน — ห้ามเผยแพร่ต่อภายนอก",
            align="C",
        )


def build_pdf():
    pdf = ThaiPDF()

    # ── Page 1 ──
    pdf.add_page()
    pdf.set_font("Thai", "B", 22)
    pdf.cell(0, 12, "รายงานวิเคราะห์ตลาดการลงทุน", align="C")
    pdf.ln(10)
    pdf.set_font("Thai", "B", 16)
    pdf.cell(0, 10, "ประจำไตรมาส 2/2569", align="C")
    pdf.ln(14)
    pdf.set_font("Thai", "", 10)
    detail_lines = [
        "จัดทำโดย: ฝ่ายวิจัยและวิเคราะห์การลงทุน",
        "วันที่ออกรายงาน: 14 กรกฎาคม 2569",
        "รหัสรายงาน: IR-Q2-2569-001",
    ]
    for line in detail_lines:
        pdf.cell(0, 6, line)
        pdf.ln(6)

    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Thai", "B", 14)
    pdf.cell(0, 8, "สารบัญ")
    pdf.ln(10)
    pdf.set_font("Thai", "", 10)
    toc = [
        ("1. บทสรุปผู้บริหาร", "1"),
        ("2. ภาพรวมเศรษฐกิจมหภาค", "2"),
        ("3. การวิเคราะห์ตลาดหลักทรัพย์", "3"),
        ("4. การลงทุนในตราสารหนี้และสินทรัพย์ทางเลือก", "4"),
        ("5. ข้อเสนอแนะเชิงกลยุทธ์", "4"),
        ("6. ภาคผนวก: สรุปตัวชี้วัดสำคัญ", "5"),
    ]
    col_w = [150, 30]
    pdf.set_font("Thai", "B", 9)
    for hdr, w in zip(["หัวข้อ", "หน้า"], col_w):
        pdf.cell(w, 7, hdr, border=1, align="C")
    pdf.ln()
    pdf.set_font("Thai", "", 9)
    for topic, page in toc:
        pdf.cell(col_w[0], 6, f"  {topic}", border=1)
        pdf.cell(col_w[1], 6, page, border=1, align="C")
        pdf.ln()
    pdf.ln(6)

    # cover page text
    pdf.set_font("Thai", "B", 12)
    pdf.cell(0, 8, "1. บทสรุปผู้บริหาร")
    pdf.ln(10)
    pdf.set_font("Thai", "", 10)
    pdf.multi_cell(0, 5.5,
        "ภาพรวมไตรมาส 2/2569 ตลาดการลงทุนไทยมีทิศทางฟื้นตัวอย่างต่อเนื่อง "
        "หลังจากปัจจัยกดดันจากอัตราดอกเบี้ยและเงินเฟ้อเริ่มคลี่คลาย "
        "ดัชนี SET Index ปิดที่ 1,489.23 จุด เพิ่มขึ้น +4.7% จากไตรมาสก่อนหน้า "
        "โดยมีแรงขับเคลื่อนหลักจาก:"
    )
    pdf.ln(2)
    bullets = [
        "การฟื้นตัวของภาคการท่องเที่ยวที่กลับมาแตะระดับ 85% ของช่วงก่อนโควิด-19",
        "กระแสเงินทุนต่างชาติ (Foreign Fund Flow) ไหลเข้าสุทธิ +32,450 ล้านบาท",
        "ผลประกอบการบริษัทจดทะเบียนไตรมาส 1/2569 ที่ออกมาดีกว่าคาดการณ์ 8.2%",
        "เสถียรภาพทางการเมืองหลังจัดตั้งรัฐบาลใหม่ได้สำเร็จ",
    ]
    for b in bullets:
        pdf.cell(5)
        pdf.cell(0, 5.5, f"- {b}")
        pdf.ln(5.5)
    pdf.ln(4)
    pdf.set_font("Thai", "B", 10)
    pdf.cell(0, 6, "อย่างไรก็ตาม ยังมีปัจจัยเสี่ยงที่ต้องติดตามอย่างใกล้ชิด")
    pdf.ln(8)

    # ── Page 2 ──
    pdf.add_page()
    pdf.set_font("Thai", "B", 14)
    pdf.cell(0, 8, "2. ภาพรวมเศรษฐกิจมหภาค")
    pdf.ln(10)
    pdf.set_font("Thai", "", 10)
    pdf.multi_cell(0, 5.5,
        "เศรษฐกิจไทยในไตรมาส 2/2569 ขยายตัวต่อเนื่องที่ 3.2% YoY "
        "(ประมาณการเบื้องต้น) โดยได้แรงหนุนจากการบริโภคภายในประเทศ "
        "และการใช้จ่ายภาครัฐ อย่างไรก็ตาม การส่งออกยังคงชะลอตัวจากภาวะเศรษฐกิจโลกที่ไม่แน่นอน"
    )
    pdf.ln(4)
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "2.1 ตัวชี้วัดเศรษฐกิจสำคัญ")
    pdf.ln(9)

    # Table 1: Economic indicators
    table1_headers = ["ตัวชี้วัด", "Q2/2569", "Q1/2569", "Q2/2568", "%Δ QoQ", "%Δ YoY"]
    table1_data = [
        ["GDP Growth (%)", "3.2", "2.8", "2.1", "+0.4 ppt", "+1.1 ppt"],
        ["อัตราเงินเฟ้อทั่วไป (%)", "1.4", "1.8", "3.2", "-0.4 ppt", "-1.8 ppt"],
        ["อัตราดอกเบี้ยนโยบาย (%)", "2.25", "2.50", "3.00", "-0.25 ppt", "-0.75 ppt"],
        ["หนี้สาธารณะต่อ GDP (%)", "58.3", "57.9", "61.2", "+0.4 ppt", "-2.9 ppt"],
        ["อัตราการว่างงาน (%)", "1.02", "1.14", "1.35", "-0.12 ppt", "-0.33 ppt"],
        ["ทุนสำรองฯ (พันล้าน USD)", "245.8", "238.4", "221.6", "+3.1%", "+10.9%"],
    ]
    col_w1 = [50, 25, 25, 25, 25, 25]
    pdf.set_font("Thai", "B", 7)
    for hdr, w in zip(table1_headers, col_w1):
        pdf.cell(w, 6, hdr, border=1, align="C")
    pdf.ln()
    pdf.set_font("Thai", "", 7)
    for row in table1_data:
        for cell, w in zip(row, col_w1):
            pdf.cell(w, 5, cell, border=1, align="C")
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Thai", "B", 10)
    pdf.cell(0, 6, "2.2 ปัจจัยขับเคลื่อนเศรษฐกิจหลัก")
    pdf.ln(8)
    pdf.set_font("Thai", "", 10)
    factors = [
        "ภาคการท่องเที่ยว: นักท่องเที่ยวต่างชาติ 8 เดือนแรก 22.4 ล้านคน (+23% YoY)",
        "การใช้จ่ายภาครัฐ: งบประมาณปี 2569 ถูกเร่งรัดเบิกจ่ายถึง 62% ในครึ่งปีแรก",
        "การลงทุนภาคเอกชน: ดัชนีความเชื่อมั่นทางธุรกิจ 49.8 จุด ปรับตัวดีขึ้นจาก 47.2",
    ]
    for f in factors:
        pdf.cell(5)
        pdf.cell(0, 5.5, f"- {f}")
        pdf.ln(5.5)
    pdf.ln(4)
    pdf.set_font("Thai", "B", 10)
    pdf.cell(0, 6, "2.3 ปัจจัยเสี่ยงที่ต้องติดตาม")
    pdf.ln(8)
    pdf.set_font("Thai", "", 10)
    risks = [
        "ความขัดแย้งทางภูมิรัฐศาสตร์ในตะวันออกลางที่อาจกระทบราคาพลังงานโลก",
        "การชะลอตัวของเศรษฐกิจจีนที่อาจลดทอนกำลังซื้อของนักท่องเที่ยว",
        "สภาพอากาศแปรปรวนจากปรากฏการณ์เอลนีโญที่อาจกระทบผลผลิตภาคการเกษตร",
        "หนี้ครัวเรือนไทยที่ยังอยู่ในระดับสูงถึง 89.6% ของ GDP",
    ]
    for i, r in enumerate(risks, 1):
        pdf.cell(5)
        pdf.cell(0, 5.5, f"{i}. {r}")
        pdf.ln(5.5)

    # ── Page 3 ──
    pdf.add_page()
    pdf.set_font("Thai", "B", 14)
    pdf.cell(0, 8, "3. การวิเคราะห์ตลาดหลักทรัพย์")
    pdf.ln(10)
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "3.1 ภาพรวม SET Index")
    pdf.ln(9)
    pdf.set_font("Thai", "", 10)
    pdf.multi_cell(0, 5.5,
        "ดัชนี SET Index ณ สิ้นไตรมาส 2/2569 ปิดที่ 1,489.23 จุด "
        "โดยมีกรอบการเคลื่อนไหวระหว่าง 1,412-1,521 จุด "
        "มูลค่าการซื้อขายเฉลี่ยต่อวันอยู่ที่ 62,450 ล้านบาท เพิ่มขึ้น 14% จากไตรมาสก่อน "
        "นักลงทุนต่างชาติซื้อสุทธิ +32,450 ล้านบาท "
        "ขณะที่นักลงทุนสถาบันขายสุทธิ -8,230 ล้านบาท"
    )
    pdf.ln(6)
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "3.2 ผลตอบแทนรายกลุ่มอุตสาหกรรม")
    pdf.ln(9)

    # Table 2: Sector performance
    t2_h = ["กลุ่มอุตสาหกรรม", "%Δ QoQ", "%Δ YTD", "P/E", "Div. Yield"]
    t2_d = [
        ["ท่องเที่ยวและสันทนาการ", "+12.4%", "+18.7%", "32.5x", "1.2%"],
        ["พาณิชย์", "+8.9%", "+11.2%", "22.1x", "2.8%"],
        ["กลุ่มธนาคาร", "+6.5%", "+7.8%", "10.4x", "5.4%"],
        ["พลังงานและสาธารณูปโภค", "+3.2%", "+2.1%", "15.8x", "4.1%"],
        ["กลุ่มเทคโนโลยี", "-2.8%", "-5.3%", "28.7x", "0.9%"],
        ["อสังหาริมทรัพย์และก่อสร้าง", "+4.5%", "+6.0%", "14.2x", "4.8%"],
        ["กลุ่มอาหารและเครื่องดื่ม", "+7.1%", "+9.5%", "19.6x", "3.4%"],
        ["SET Index โดยรวม", "+4.7%", "+6.3%", "16.8x", "3.5%"],
    ]
    col_w2 = [62, 27, 27, 27, 27]
    pdf.set_font("Thai", "B", 7)
    for h, w in zip(t2_h, col_w2):
        pdf.cell(w, 6, h, border=1, align="C")
    pdf.ln()
    pdf.set_font("Thai", "", 7)
    for row in t2_d:
        for c, w in zip(row, col_w2):
            pdf.cell(w, 5, c, border=1, align="C")
        pdf.ln()
    pdf.ln(6)

    # Table 3: Stock picks
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "3.3 หุ้นเด่นที่น่าจับตา")
    pdf.ln(9)
    t3_h = ["บริษัท", " ticker", "ราคา", "แนวรับ", "แนวต้าน", "คำแนะนำ"]
    t3_d = [
        ["บมจ. ท่องเที่ยวไทย", "AOT", "78.50", "74.00", "84.00", "ซื้อ"],
        ["บมจ. ธนาคารกรุงไทย", "KTB", "22.10", "20.50", "24.20", "ซื้อ"],
        ["บมจ. ซีพี ออลล์", "CPALL", "68.25", "63.00", "73.50", "ซื้อสะสม"],
        ["บมจ. ปูนซิเมนต์ไทย", "SCC", "258.00", "242.00", "278.00", "ถือ"],
    ]
    col_w3 = [56, 20, 27, 27, 27, 27]
    pdf.set_font("Thai", "B", 7)
    for h, w in zip(t3_h, col_w3):
        pdf.cell(w, 6, h, border=1, align="C")
    pdf.ln()
    pdf.set_font("Thai", "", 7)
    for row in t3_d:
        for c, w in zip(row, col_w3):
            pdf.cell(w, 5, c, border=1, align="C")
        pdf.ln()

    # ── Page 4 ──
    pdf.add_page()
    pdf.set_font("Thai", "B", 14)
    pdf.cell(0, 8, "4. การลงทุนในตราสารหนี้และสินทรัพย์ทางเลือก")
    pdf.ln(10)
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "4.1 ภาพรวมตลาดตราสารหนี้")
    pdf.ln(9)
    pdf.set_font("Thai", "", 10)
    pdf.multi_cell(0, 5.5,
        "อัตราผลตอบแทนพันธบัตรรัฐบาล (Government Bond Yield) "
        "ปรับตัวลดลงต่อเนื่องจากไตรมาสก่อน "
        "สะท้อนความคาดหวังของตลาดที่ว่าธนาคารแห่งประเทศไทย "
        "จะปรับลดอัตราดอกเบี้ยนโยบายลงอีก 0.25% "
        "ในการประชุมเดือนสิงหาคมนี้"
    )
    pdf.ln(6)

    # Table 4: Bond yields
    t4_h = ["อายุคงเหลือ", "Yield ปัจจุบัน", "Yield ไตรมาสก่อน", "เปลี่ยนแปลง (bps)"]
    t4_d = [
        ["1 ปี", "2.12%", "2.45%", "-33 bps"],
        ["3 ปี", "2.45%", "2.78%", "-33 bps"],
        ["5 ปี", "2.68%", "3.02%", "-34 bps"],
        ["10 ปี", "3.15%", "3.48%", "-33 bps"],
        ["15 ปี", "3.52%", "3.80%", "-28 bps"],
        ["30 ปี", "3.88%", "4.10%", "-22 bps"],
    ]
    col_w4 = [40, 40, 45, 45]
    pdf.set_font("Thai", "B", 8)
    for h, w in zip(t4_h, col_w4):
        pdf.cell(w, 6, h, border=1, align="C")
    pdf.ln()
    pdf.set_font("Thai", "", 8)
    for row in t4_d:
        for c, w in zip(row, col_w4):
            pdf.cell(w, 5, c, border=1, align="C")
        pdf.ln()

    pdf.ln(6)
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "4.2 สินทรัพย์ทางเลือก")
    pdf.ln(9)
    pdf.set_font("Thai", "", 10)
    alts = [
        "ทองคำ: ราคาทองคำในประเทศปรับตัวขึ้นสู่ระดับ 42,500 บาท/บาททองคำ (+12% YTD)",
        "REIT: ให้ผลตอบแทนเฉลี่ย 6.8% ต่อปี โดยกลุ่มค้าปลีกและโรงแรม outperformance",
        "สกุลเงินดิจิทัล: Bitcoin ปรับตัวขึ้น 45% ในไตรมาสนี้แตะ 1.8 ล้านบาท",
    ]
    for a in alts:
        pdf.cell(5)
        pdf.cell(0, 5.5, f"- {a}")
        pdf.ln(5.5)

    pdf.ln(6)
    pdf.set_font("Thai", "B", 14)
    pdf.cell(0, 8, "5. ข้อเสนอแนะเชิงกลยุทธ์")
    pdf.ln(10)
    pdf.set_font("Thai", "B", 10)
    pdf.cell(0, 6, "สำหรับนักลงทุนระยะสั้น (1-3 เดือน)")
    pdf.ln(8)
    pdf.set_font("Thai", "", 10)
    short_term = [
        "เน้นสะสมหุ้นกลุ่มท่องเที่ยว ค้าปลีก และธนาคารในช่วงที่ตลาดอ่อนตัว",
        "ตั้งจุดตัดขาดทุน (Stop Loss) ไม่เกิน 7-10% จากราคาซื้อ",
        "ติดตามการประชุม กนง. ในเดือนสิงหาคมอย่างใกล้ชิด",
    ]
    for s in short_term:
        pdf.cell(5)
        pdf.cell(0, 5.5, f"- {s}")
        pdf.ln(5.5)

    # ── Page 5 ──
    pdf.add_page()
    pdf.set_font("Thai", "B", 14)
    pdf.cell(0, 8, "6. ภาคผนวก: สรุปตัวชี้วัดสำคัญ")
    pdf.ln(10)
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "6.1 ตารางสรุปตัวชี้วัดการลงทุน")
    pdf.ln(9)

    t5_h = ["รายการ", "ค่า ณ สิ้นไตรมาส", "% เปลี่ยนแปลง"]
    t5_d = [
        ["SET Index", "1,489.23 จุด", "+4.7% (QoQ)"],
        ["SET50 Index", "982.45 จุด", "+5.1% (QoQ)"],
        ["mai Index", "524.78 จุด", "+3.2% (QoQ)"],
        ["มูลค่าซื้อขายเฉลี่ย/วัน", "62,450 ล้านบาท", "+14.0% (QoQ)"],
        ["Foreign Flow (สุทธิ)", "+32,450 ล้านบาท", "—"],
        ["Market Cap SET", "19.8 ล้านล้านบาท", "+4.9% (QoQ)"],
        ["P/E Ratio SET", "16.8 เท่า", "ทรงตัว"],
        ["Dividend Yield SET", "3.5%", "+0.2 ppt"],
    ]
    col_w5 = [65, 60, 50]
    pdf.set_font("Thai", "B", 8)
    for h, w in zip(t5_h, col_w5):
        pdf.cell(w, 6, h, border=1, align="C")
    pdf.ln()
    pdf.set_font("Thai", "", 8)
    for row in t5_d:
        for c, w in zip(row, col_w5):
            pdf.cell(w, 5, c, border=1, align="C")
        pdf.ln()

    pdf.ln(8)
    pdf.set_font("Thai", "B", 11)
    pdf.cell(0, 7, "6.2 ปฏิทินเศรษฐกิจสำคัญ (ไตรมาส 3/2569)")
    pdf.ln(9)
    pdf.set_font("Thai", "", 10)
    calendar = [
        "14 ส.ค. 2569 — ประชุมคณะกรรมการนโยบายการเงิน (กนง.)",
        "20 ส.ค. 2569 — ประกาศ GDP ไทย ไตรมาส 2/2569",
        "1-5 ก.ย. 2569 — งาน Opportunity Day บจ.",
        "15 ก.ย. 2569 — ประชุม FOMC ธนาคารกลางสหรัฐฯ",
        "30 ก.ย. 2569 — วันสิ้นสุดไตรมาส 3/2569",
    ]
    for evt in calendar:
        pdf.cell(5)
        pdf.cell(0, 5.5, f"- {evt}")
        pdf.ln(5.5)

    pdf.ln(8)
    pdf.set_font("Thai", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5,
        "คำปฏิเสธความรับผิดชอบ: รายงานฉบับนี้จัดทำขึ้นโดยฝ่ายวิจัยและวิเคราะห์การลงทุน "
        "โดยมีวัตถุประสงค์เพื่อให้ข้อมูลเท่านั้น มิได้เป็นการชักชวนให้ซื้อหรือขายหลักทรัพย์ใดๆ "
        "การตัดสินใจลงทุนขึ้นอยู่กับดุลยพินิจของนักลงทุน"
    )

    pdf.output(OUTPUT)
    print(f"✅ PDF created: {OUTPUT}")
    print(f"   Pages: {pdf.page_no()}")
    print(f"   Size: {OUTPUT.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    build_pdf()
