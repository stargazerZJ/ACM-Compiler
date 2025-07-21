; Function Declaration
declare i32 @foo()
declare i1 @getcond()

define i32 @main() {
block1:
  %t1 = call i32 @foo()
  br label %block2

block2:
  %t2 = phi i32 [ %t1, %block1 ], [%t3, %block6 ]
  %t3 = add i32 %t2, 1
  %cond = call i1 @getcond()
  br i1 %cond, label %block3, label %block_exit

block3:
  %cond2 = call i1 @getcond()
  br i1 %cond2, label %block4, label %block5

block4:
  %t4 = add i32 %t2, %t3
  %t6 = add i32 %t1, %t4
  br label %block6

block5:
  %t7 = add i32 %t3, 1
  br label %block6

block6:
  %t8 = phi i32 [ %t1, %block4 ], [ %t7, %block5 ]
  %t9 = add i32 %t2, %t3
  %t10 = add i32 %t9, %t8
  %t11 = call i32 @foo()
  %t12 = add i32 %t9, %t11
  %t13 = add i32 %t12, %t3
  br label %block2

block_exit:
  ret i32 0
}