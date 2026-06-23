import streamlit as st
import pandas as pd
import numpy as np
import datetime
import altair as alt

# إعدادات الصفحة العامة
st.set_page_config(page_title="AC Simulator", layout="wide")

# --- نظام التنقل بين الصفحات ---
page = st.sidebar.radio("📂 Choose Page:", ["🏠 Main Dashboard", "⚙️ Advanced Settings"])

# تجميع وحفظ الإعدادات الافتراضية عبر الـ Session State
if 'setpoint' not in st.session_state: st.session_state.setpoint = 23.0
if 'base_outdoor_temp' not in st.session_state: st.session_state.base_outdoor_temp = 34.0
if 'temp_amplitude' not in st.session_state: st.session_state.temp_amplitude = 8.0
if 'initial_room_temp' not in st.session_state: st.session_state.initial_room_temp = 25.0
if 'normal_current' not in st.session_state: st.session_state.normal_current = 11.5
if 'target_suction_press' not in st.session_state: st.session_state.target_suction_press = 118.0
if 'normal_superheat' not in st.session_state: st.session_state.normal_superheat = 6.5
if 'ac_mode' not in st.session_state: st.session_state.ac_mode = "Cool"

# --- محتوى القائمة الجانبية ---
if page == "🏠 Main Dashboard":
    st.sidebar.header("🎛️ Main Settings")
    st.session_state.setpoint = st.sidebar.number_input("Temperature Setpoint (°C)", min_value=16.0, max_value=30.0, value=st.session_state.setpoint, step=0.5)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("❄️ AC Mode")
    st.session_state.ac_mode = st.sidebar.selectbox("Choose AC Mode", ["Cool", "Dry", "Fan"])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🌡️ Average Outdoor Temperature")
    st.session_state.base_outdoor_temp = st.sidebar.slider("Average Outdoor Temperature (°C)", min_value=20.0, max_value=50.0, value=st.session_state.base_outdoor_temp, step=1.0)
    st.session_state.temp_amplitude = st.sidebar.slider("Outdoor Temperature Amplitude (°C)", min_value=0.0, max_value=15.0, value=st.session_state.temp_amplitude, step=0.5)

else:
    st.sidebar.header("⚙️ Advanced Sensors and Settings")
    st.session_state.initial_room_temp = st.sidebar.number_input("Initial Room Temperature (°C)", min_value=16.0, max_value=40.0, value=st.session_state.initial_room_temp, step=0.5)
    st.session_state.normal_current = st.sidebar.number_input("Normal Compressor Current (Amps)", min_value=5.0, max_value=25.0, value=st.session_state.normal_current, step=0.5)
    st.session_state.target_suction_press = st.sidebar.number_input("Target Suction Pressure (PSI)", min_value=90.0, max_value=150.0, value=st.session_state.target_suction_press, step=1.0)
    st.session_state.normal_superheat = st.sidebar.number_input("Normal Superheat (°C)", min_value=2.0, max_value=15.0, value=st.session_state.normal_superheat, step=0.5)

# --- محرك المحاكاة وتوليد البيانات (24 ساعة بنظام قراءة كل 5 دقائق = 288 قراءة واقعية وسريعة) ---
intervals = 24 * 12  
timestamps = [datetime.datetime(2026, 6, 23, 0, 0) + datetime.timedelta(minutes=5*i) for i in range(intervals)]
outdoor_temps = [round(st.session_state.base_outdoor_temp + st.session_state.temp_amplitude * np.sin((ts.hour + ts.minute/60.0 - 9) * np.pi / 12) + np.random.normal(0, 0.15), 1) for ts in timestamps]

room_temp = st.session_state.initial_room_temp
compressor_status = 0
data = []
cumulative_energy = 0.0

# حدود الـ Hysteresis الفنية للمكيف
upper_bound = st.session_state.setpoint + 0.5
lower_bound = st.session_state.setpoint - 0.5

for i, ts in enumerate(timestamps):
    out_temp = outdoor_temps[i]
    hour = ts.hour + ts.minute / 60.0
    
    # منطق التحكم بالتشغيل والفصل التلقائي (Hysteresis Control)
    if room_temp >= upper_bound:
        compressor_status = 1
    elif room_temp <= lower_bound:
        compressor_status = 0
        
    # محاكاة السلوك الفيزيائي الحقيقي للمكيف وأنماط تشغيله
    if st.session_state.ac_mode == "Fan":
        compressor_status = 0  
        room_temp += 0.038 * (out_temp - room_temp) # تأثر سريع بالوسط الخارجي بدون تبريد
    elif st.session_state.ac_mode == "Dry":
        if room_temp > st.session_state.setpoint:
            compressor_status = 1 if (i % 6 < 3) else 0 # تشغيل دوري متقطع لسحب الرطوبة
        else:
            compressor_status = 0
        room_temp += (-0.32 if compressor_status == 1 else 0.07) * (out_temp - room_temp) * 0.12
    else: # Cool Mode (وضع التبريد الطبيعي الفعال)
        if compressor_status == 1:
            # تبريد ممتاز: ينخفض من 0.14 إلى 0.24 درجة كل 5 دقائق حسب شدة حرارة الطقس الخارجي
            cooling_delta = 0.22 - 0.002 * (out_temp - room_temp)
            room_temp -= max(0.1, cooling_delta)
        else:
            # فقد البرودة: صعود طبيعي لحرارة الغرفة نتيجة الحمل الحراري الخارجي والعزل
            heating_delta = 0.024 * (out_temp - room_temp)
            room_temp += max(0.01, heating_delta)
            
    # إضافة تذبذب تيار الهواء الطبيعي العشوائي داخل الغرفة
    room_temp += np.random.normal(0, 0.015)
    
    # محاكاة الرطوبة بناء على حالة عمل المكيف
    if compressor_status == 1 or st.session_state.ac_mode == "Dry":
        humidity = max(35, 44.0 - 4 * (1 - np.exp(-0.2 * (i % 8))) + np.random.normal(0, 0.4))
    else:
        humidity = min(72, 54.0 + 5 * (1 - np.exp(-0.1 * (i % 12))) + np.random.normal(0, 0.4))
        
    # الحسابات الكهربائية والميكانيكية الفورية لكل قراءة
    if compressor_status == 1:
        current = st.session_state.normal_current + 0.06 * (out_temp - st.session_state.base_outdoor_temp) + np.random.normal(0, 0.06)
        power_kw = (current * 230 * 0.88) / 1000.0  
        suction_press = st.session_state.target_suction_press + np.random.normal(0, 0.4)
        superheat = st.session_state.normal_superheat + np.random.normal(0, 0.1)
    else:
        current = 0.70 + np.random.normal(0, 0.01) # المروحة الداخلية فقط عند فصل الكمبرسور
        power_kw = (current * 230 * 0.95) / 1000.0 
        suction_press = (st.session_state.target_suction_press + 55) - 45 * np.exp(-0.3 * (i % 6))
        superheat = 0.0
        
    cumulative_energy += power_kw * (5 / 60.0) # إضافة الاستهلاك الفعلي لخطوة الـ 5 دقائق
    
    data.append({
        "Timestamp": ts.strftime("%H:%M"),
        "Outdoor Temp (°C)": round(out_temp, 1),
        "Setpoint (°C)": st.session_state.setpoint,
        "Room Temp (°C)": round(room_temp, 2),
        "Humidity (%)": round(humidity, 1),
        "AC Mode": st.session_state.ac_mode,
        "Compressor Status": "ON" if compressor_status == 1 else "OFF",
        "Current (A)": round(current, 2),
        "Est. Power (Watt)": round(power_kw * 1000, 1),
        "Suction Pressure (PSI)": round(suction_press, 1),
        "Superheat (°C)": round(superheat, 1),
        "Cumulative Energy (kWh)": round(cumulative_energy, 3)
    })

df = pd.DataFrame(data)

# --- عرض المخرجات والواجهات بحسب الصفحة المحددة ---
if page == "🏠 Main Dashboard":
    st.title("📊 Main AC Control and Simulation Dashboard")
    
    # 1. المتركس العلوية بنفس توزيعك وشكلك خماسي الأعمدة الأصلي
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current Operating Mode", st.session_state.ac_mode)
    c2.metric("Compressor Status", "ON" if compressor_status == 1 else "OFF")
    c3.metric("Current Room Temperature", f"{round(room_temp, 2)} °C")
    c4.metric("Current Room Humidity", f"{round(humidity, 1)} %")
    c5.metric("Cumulative Energy Consumption", f"{round(cumulative_energy, 2)} kWh") 
    
    st.markdown("---")
    
    # عنوان وعناصر التحكم الجانبية بالترند
    st.subheader("Interactivity Trend Analysis")
    
    # إنشاء عمودين: يسار للرسمة، ويمين لقائمة الفلاتر (البراميترز)
    col_chart, col_controls = st.columns([5, 1])
    
    with col_controls:
        st.markdown("**📌 Show/Hide Metrics:**")
        show_room_temp = st.checkbox("Room Temperature (°C)", value=True)
        show_setpoint = st.checkbox("Setpoint (°C)", value=True)
        show_outdoor_temp = st.checkbox("Outdoor Temperature (°C)", value=False)
        show_current = st.checkbox("Current (A)", value=True)
        show_power = st.checkbox("Power (Watt)", value=False)

    # تحويل البيانات لتناسب فلترة الرسم الديناميكي
    df_melted = df.melt(id_vars=["Timestamp"], value_vars=["Room Temp (°C)", "Outdoor Temp (°C)", "Setpoint (°C)", "Current (A)", "Est. Power (Watt)"], var_name="Metric", value_name="Value")

    # تحديد الفلاتر النشطة بناءً على اختيارات المستخدم
    active_metrics = []
    if show_room_temp: active_metrics.append("Room Temp (°C)")
    if show_setpoint: active_metrics.append("Setpoint (°C)")
    if show_outdoor_temp: active_metrics.append("Outdoor Temp (°C)")
    if show_current: active_metrics.append("Current (A)")
    if show_power: active_metrics.append("Est. Power (Watt)")

    df_filtered = df_melted[df_melted["Metric"].isin(active_metrics)]

    with col_chart:
        if len(active_metrics) == 0:
            st.warning("⚠️ Please select at least one metric from the sidebar to display in the chart.")
        else:
            # فصل الطبقة اليسرى (حرارة الغرفة والـ Setpoint فقط)
            left_metrics = [m for m in active_metrics if m in ["Room Temp (°C)", "Setpoint (°C)"]]
            # بقية العناصر تذهب للطبقة اليمنى
            right_metrics = [m for m in active_metrics if m in ["Outdoor Temp (°C)", "Current (A)", "Est. Power (Watt)"]]
            
            layers = []
            
            # بناء محور اليسار
            if left_metrics:
                left_chart = alt.Chart(df_filtered[df_filtered["Metric"].isin(left_metrics)]).encode(
                    x=alt.X("Timestamp:N", title="Time of Day"),
                    y=alt.Y("Value:Q", title="🌡️ Left Axis: Room Temperature and Setpoint (°C)", scale=alt.Scale(zero=False)),
                    color=alt.Color("Metric:N", scale=alt.Scale(domain=["Room Temp (°C)", "Setpoint (°C)"], range=["blue", "green"]))
                ).mark_line(strokeWidth=2.5)
                layers.append(left_chart)
                
            # بناء محور اليمين
            if right_metrics:
                right_chart = alt.Chart(df_filtered[df_filtered["Metric"].isin(right_metrics)]).encode(
                    x=alt.X("Timestamp:N"),
                    y=alt.Y("Value:Q", title="⚡ Right Axis: Various Mechanical and Electrical Indicators", scale=alt.Scale(zero=False)),
                    color=alt.Color("Metric:N", scale=alt.Scale(domain=["Outdoor Temp (°C)", "Current (A)", "Est. Power (Watt)"], range=["orange", "red", "purple"]))
                ).mark_line(strokeWidth=2)
                layers.append(right_chart)

            # دمج وفصل موازين السكيل هندسياً
            if len(layers) == 2:
                final_chart = alt.layer(layers[0], layers[1]).resolve_scale(y='independent').properties(width='container', height=500)
            else:
                final_chart = layers[0].properties(width='container', height=500)
                
            st.altair_chart(final_chart, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Detailed Time-Series Readings for Raw Data")
    st.dataframe(df, use_container_width=True)
    
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Download Complete Raw Data as CSV", data=csv_data, file_name='AC_Simulated_Raw_Data.csv', mime='text/csv')

elif page == "Advanced Settings":
    st.title("⚙️ Advanced Sensor and Metric Control Panel")
    
    col_a, col_b = st.columns(2)
    col_a.metric("Average Suction Pressure", f"{round(df['Suction Pressure (PSI)'].mean(), 1)} PSI")
    col_b.metric("Average Superheat", f"{round(df['Superheat (°C)'].mean(), 1)} °C")
    
    st.markdown("---")
    st.subheader("📊 Suction Pressure and Superheat Chart with Independent Axes")
    
    df_adv_melted = df.melt(id_vars=["Timestamp"], value_vars=["Suction Pressure (PSI)", "Superheat (°C)"], var_name="Metric", value_name="Value")
    
    chart_press = alt.Chart(df_adv_melted[df_adv_melted["Metric"] == "Suction Pressure (PSI)"]).encode(
        x="Timestamp:N", y=alt.Y("Value:Q", title="Suction Pressure (PSI)", scale=alt.Scale(zero=False)), color=alt.value("teal")
    ).mark_line()
    
    chart_sh = alt.Chart(df_adv_melted[df_adv_melted["Metric"] == "Superheat (°C)"]).encode(
        x="Timestamp:N", y=alt.Y("Value:Q", title="Superheat (°C)", scale=alt.Scale(zero=False)), color=alt.value("magenta")
    ).mark_line()
    
    adv_chart = alt.layer(chart_press, chart_sh).resolve_scale(y='independent').properties(width='container', height=400)
    st.altair_chart(adv_chart, use_container_width=True)